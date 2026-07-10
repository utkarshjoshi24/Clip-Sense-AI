"""
audio_energy.py — Stage 1: Audio extraction and energy analysis.

Extracts audio from a video file using ffmpeg, then computes a smoothed
RMS energy curve using librosa and identifies energy peaks using scipy.

Public functions:
    extract_audio(video_path, cache_dir) -> Path
    analyze_energy(audio_path, cache_key, cache_dir) -> list[tuple[float, float]]
"""

import json
import subprocess
import sys
from pathlib import Path

import librosa
import numpy as np
from scipy.signal import find_peaks, savgol_filter

from . import config
from .error_handler import (
    FFmpegError,
    PermissionDeniedError,
    VideoFormatError,
    get_logger,
)


def extract_audio(video_path: str | Path, cache_dir: Path) -> Path:
    """Extract mono WAV audio from a video file using ffmpeg.

    Args:
        video_path: Path to the source video file.
        cache_dir: Directory to store the extracted audio file.

    Returns:
        Path to the extracted .wav file.
    """
    video_path = Path(video_path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_path = cache_dir / "audio.wav"

    if output_path.exists():
        print("  ✓ Audio already extracted (cached), skipping ffmpeg.")
        return output_path

    print("  ⏳ Extracting audio from video with ffmpeg...")

    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vn",                  # no video
        "-acodec", "pcm_s16le", # 16-bit PCM
        "-ar", "22050",         # 22050 Hz sample rate (good for speech + music)
        "-ac", "1",             # mono
        "-y",                   # overwrite if exists
        str(output_path),
    ]

    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except FileNotFoundError:
        raise FFmpegError(
            user_message=(
                "❌ ffmpeg not found. Cannot extract audio from video.\n"
                "   ClipSense requires ffmpeg for audio processing.\n"
                "\n"
                "   If you installed via .pkg, try reinstalling ClipSense.\n"
                "   To install manually: brew install ffmpeg"
            ),
            detail="ffmpeg binary not found in PATH during audio extraction",
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode()[:500] if e.stderr else "unknown error"
        logger = get_logger()
        logger.error("ffmpeg audio extraction failed: %s", stderr)

        if "Permission denied" in stderr or "Operation not permitted" in stderr:
            raise PermissionDeniedError(
                path=str(video_path),
                operation="read",
                detail=f"ffmpeg permission denied: {stderr}",
            )
        elif "Invalid data" in stderr or "does not contain" in stderr:
            raise VideoFormatError(
                video_path=str(video_path),
                detail=f"ffmpeg audio extraction error: {stderr}",
            )
        else:
            raise FFmpegError(
                user_message=(
                    f"❌ ffmpeg failed to extract audio from this video.\n"
                    f"   The video may be corrupted or use an unsupported format.\n"
                    f"   Error: {stderr[:200]}"
                ),
                detail=f"ffmpeg CalledProcessError: {stderr}",
            )

    print(f"  ✓ Audio extracted → {output_path}")
    return output_path


def analyze_energy(
    audio_path: str | Path,
    cache_key: str,
    cache_dir: Path,
) -> list[tuple[float, float]]:
    """Compute RMS energy curve and identify peaks.

    Steps:
        1. Load audio with librosa.
        2. Compute RMS energy in short windows.
        3. Normalize to 0–1.
        4. Smooth with Savitzky-Golay filter.
        5. Find peaks with scipy.signal.find_peaks.
        6. Cache results.

    Args:
        audio_path: Path to the .wav audio file.
        cache_key: Unique key for caching (derived from video file identity).
        cache_dir: Directory to store cached results.

    Returns:
        List of (timestamp_seconds, energy_score) tuples for each detected peak.
        energy_score is normalized 0–1.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"energy_{cache_key}.json"

    # Check cache
    if cache_file.exists():
        print("  ✓ Audio energy analysis found in cache, loading...")
        with open(cache_file, "r") as f:
            cached = json.load(f)
        return [(p["timestamp"], p["score"]) for p in cached["peaks"]]

    print("  ⏳ Computing RMS energy curve with librosa...")

    # Load audio
    y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)
    print(f"    Audio duration: {duration:.1f}s ({duration/60:.1f} min)")

    # Compute RMS energy
    hop_length = int(config.RMS_WINDOW_SEC * sr)
    rms = librosa.feature.rms(y=y, frame_length=hop_length * 2, hop_length=hop_length)[0]

    # Normalize to 0–1
    rms_min = rms.min()
    rms_max = rms.max()
    if rms_max - rms_min > 0:
        rms_norm = (rms - rms_min) / (rms_max - rms_min)
    else:
        rms_norm = np.zeros_like(rms)

    # Smooth with Savitzky-Golay filter
    window_len = config.ENERGY_SMOOTHING_WINDOW
    if len(rms_norm) < window_len:
        window_len = len(rms_norm) if len(rms_norm) % 2 == 1 else len(rms_norm) - 1
    if window_len >= 3:
        rms_smooth = savgol_filter(rms_norm, window_len, config.ENERGY_SMOOTHING_POLY)
        # Clip to 0–1 after smoothing (filter can overshoot slightly)
        rms_smooth = np.clip(rms_smooth, 0, 1)
    else:
        rms_smooth = rms_norm

    # Find peaks
    peaks_idx, properties = find_peaks(
        rms_smooth,
        prominence=config.PEAK_PROMINENCE,
        distance=config.PEAK_DISTANCE,
    )

    # Convert frame indices to timestamps
    times = librosa.frames_to_time(
        np.arange(len(rms_smooth)),
        sr=sr,
        hop_length=hop_length,
    )

    peaks = []
    for idx in peaks_idx:
        peaks.append({
            "timestamp": float(times[idx]),
            "score": float(rms_smooth[idx]),
        })

    print(f"  ✓ Found {len(peaks)} energy peaks across {duration:.0f}s of audio.")

    # Also store the full energy curve for debugging / visualization
    energy_curve = [
        {"timestamp": float(times[i]), "energy": float(rms_smooth[i])}
        for i in range(len(rms_smooth))
    ]

    # Cache
    cache_data = {
        "duration": duration,
        "num_frames": len(rms_smooth),
        "peaks": peaks,
        "energy_curve": energy_curve,
    }
    with open(cache_file, "w") as f:
        json.dump(cache_data, f, indent=2)

    return [(p["timestamp"], p["score"]) for p in peaks]

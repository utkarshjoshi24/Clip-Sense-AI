"""
cli.py — Entry point for highlight-detect.

Orchestrates the 4-stage pipeline: audio energy → scene detection →
transcription → scoring, then outputs results as a terminal table and JSON.

Usage:
    python -m highlight_detect.cli VIDEO_PATH [options]
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import config
from .audio_energy import extract_audio, analyze_energy
from .scene_detect import detect_scenes, detect_scenes_full, export_all_scenes
from .transcribe import transcribe_audio, compute_lexical_signal
from .scorer import score_windows, deduplicate_windows
from .error_handler import (
    setup_logging,
    handle_exception,
    check_disk_space,
    check_permissions,
    ClipSenseError,
    FFmpegError,
    PermissionDeniedError,
    VideoFormatError,
)
from .startup_checks import run_all_checks


def _compute_cache_key(video_path: Path) -> str:
    """Compute a cache key from video file identity.

    Uses filename + file size + modification time to avoid hashing
    multi-GB files. Fast and catches re-encodes.
    """
    stat = video_path.stat()
    identity = f"{video_path.name}|{stat.st_size}|{stat.st_mtime}"
    return hashlib.sha256(identity.encode()).hexdigest()[:16]


def _get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except FileNotFoundError:
        print("⚠  ffprobe not found — video duration will be estimated from audio.")
        return 0.0
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        # Check for permission errors
        if "Permission denied" in stderr or "Operation not permitted" in stderr:
            raise PermissionDeniedError(
                path=str(video_path),
                operation="read",
                detail=f"ffprobe permission denied: {stderr[:200]}",
            )
        # Check for format errors
        if "Invalid data" in stderr or "no such file" in stderr.lower():
            raise VideoFormatError(
                video_path=str(video_path),
                detail=f"ffprobe error: {stderr[:200]}",
            )
        print("⚠  Could not determine video duration via ffprobe, "
              "will estimate from audio.")
        return 0.0
    except ValueError:
        print("⚠  Could not parse video duration from ffprobe output.")
        return 0.0


def _format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS or MM:SS.s."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    
    # If it's a whole number, format as integer
    if s % 1 == 0:
        if h > 0:
            return f"{h:02d}:{m:02d}:{int(s):02d}"
        return f"{m:02d}:{int(s):02d}"
        
    # Include 1 decimal place for sub-second precision
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:04.1f}"
    return f"{m:02d}:{s:04.1f}"


def _get_transcript_for_window(
    transcript_segments: list[dict],
    start: float,
    end: float,
    max_chars: int = 120,
) -> str:
    """Extract and truncate transcript text for a given time window."""
    texts = []
    for seg in transcript_segments:
        if seg["end"] >= start and seg["start"] <= end:
            texts.append(seg["text"])

    full_text = " ".join(texts).strip()
    if len(full_text) > max_chars:
        return full_text[:max_chars - 3] + "..."
    return full_text


def _print_results_table(highlights: list[dict], transcript_segments: list[dict]):
    """Print a formatted results table to the terminal."""
    try:
        from tabulate import tabulate
        use_tabulate = True
    except ImportError:
        use_tabulate = False

    rows = []
    for i, h in enumerate(highlights, 1):
        transcript_preview = _get_transcript_for_window(
            transcript_segments, h["start"], h["end"]
        )
        rows.append([
            i,
            _format_time(h["start"]),
            _format_time(h["end"]),
            _format_time(h["duration"]),
            f"{h['score']:.4f}",
            f"{h['audio_score']:.2f}",
            f"{h['scene_score']:.2f}",
            f"{h['lexical_score']:.2f}",
            transcript_preview,
        ])

    headers = [
        "Rank", "Start", "End", "Duration", "Score",
        "Audio", "Scene", "Lexical", "Transcript Preview"
    ]

    print("\n" + "=" * 100)
    print("  🎬  HIGHLIGHT CANDIDATES (ranked by composite score)")
    print("=" * 100)

    if use_tabulate:
        print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))
    else:
        # Manual formatting fallback
        print(f"{'Rank':>4}  {'Start':>8}  {'End':>8}  {'Dur':>8}  "
              f"{'Score':>7}  {'Audio':>5}  {'Scene':>5}  {'Lex':>5}  Transcript")
        print("-" * 100)
        for row in rows:
            print(f"{row[0]:>4}  {row[1]:>8}  {row[2]:>8}  {row[3]:>8}  "
                  f"{row[4]:>7}  {row[5]:>5}  {row[6]:>5}  {row[7]:>5}  {row[8]}")

    print()


def _export_clips(
    highlights: list[dict],
    video_path: Path,
    output_dir: Path,
):
    """Use ffmpeg to cut each highlight clip from the source video."""
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📦 Exporting {len(highlights)} clips to {output_dir}/")

    for i, h in enumerate(highlights, 1):
        output_file = output_dir / f"highlight_{i:02d}_{_format_time(h['start']).replace(':', '')}-{_format_time(h['end']).replace(':', '')}.mp4"

        cmd = [
            "ffmpeg",
            "-ss", str(h["start"]),
            "-i", str(video_path),
            "-t", str(h["duration"]),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-avoid_negative_ts", "make_zero",
            "-y",
            str(output_file),
        ]

        print(f"  ⏳ Cutting clip {i}/{len(highlights)}: "
              f"{_format_time(h['start'])} → {_format_time(h['end'])}...")

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            print(f"  ✓ → {output_file.name}")
        except FileNotFoundError:
            raise FFmpegError(
                user_message=(
                    "❌ ffmpeg not found. Cannot export clips.\n"
                    "   Install ffmpeg: brew install ffmpeg\n"
                    "   Or reinstall ClipSense to restore the bundled ffmpeg."
                ),
                detail="ffmpeg binary not found during clip export",
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode()[:300] if e.stderr else "unknown error"
            if "Permission denied" in stderr:
                raise PermissionDeniedError(
                    path=str(output_file),
                    operation="write",
                    detail=f"ffmpeg write permission denied: {stderr}",
                )
            print(f"  ✗ Failed to export clip {i}: {stderr[:200]}")

    print(f"\n✓ All clips exported to {output_dir}/")


def main():
    parser = argparse.ArgumentParser(
        prog="highlight-detect",
        description="Analyze a video and identify candidate highlight clips.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m highlight_detect.cli video.mp4
  python -m highlight_detect.cli video.mp4 --top-n 5 --min-clip-length 30
  python -m highlight_detect.cli video.mp4 --export-clips --output-dir ./clips
        """,
    )

    parser.add_argument(
        "video",
        type=str,
        help="Path to the input video file (mp4/mov).",
    )
    parser.add_argument(
        "--min-clip-length",
        type=float,
        default=60.0,
        help="Minimum clip length in seconds (default: 60.0).",
    )
    parser.add_argument(
        "--max-clip-length",
        type=float,
        default=600.0,
        help="Maximum clip length in seconds (default: 600.0).",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of candidate highlight clips to return (default: 10).",
    )
    parser.add_argument(
        "--export-clips",
        action="store_true",
        help="Export each candidate clip as a separate mp4 file.",
    )
    parser.add_argument(
        "--scene-cut",
        action="store_true",
        help="Scene-cut mode: detect ALL scene changes and export every "
             "scene as a separate mp4 into a scenes/ folder. Skips the "
             "highlight scoring pipeline entirely.",
    )
    parser.add_argument(
        "--scene-threshold",
        type=float,
        default=None,
        help="ContentDetector threshold for --scene-cut mode. Lower = more "
             "sensitive to camera angle / movement changes (default: 27.0). "
             "Try 20.0 or 15.0 for more cuts.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for output files (default: ./output).",
    )
    parser.add_argument(
        "--skip-startup-checks",
        action="store_true",
        help="Skip startup validation checks (architecture, ffmpeg, etc.).",
    )

    args = parser.parse_args()

    # --- Initialize logging ---
    logger = setup_logging()

    try:
        # --- Startup checks ---
        if not args.skip_startup_checks:
            print("🔍 Running startup checks...")
            warnings = run_all_checks()
            for w in warnings:
                print(f"\n{w}")
            if warnings:
                print()  # Extra newline after warnings
            else:
                print("  ✓ All checks passed.\n")

        # --- Validate input ---
        video_path = Path(args.video).resolve()
        if not video_path.exists():
            print(f"✗ Video file not found: {video_path}")
            sys.exit(1)

        if not video_path.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
            print(f"⚠  Unexpected file extension '{video_path.suffix}'. "
                  "Proceeding anyway, but ffmpeg may fail.")

        # Permission check on video file
        check_permissions(video_path, need_write=False)

        output_dir = Path(args.output_dir) if args.output_dir else config.OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        # Permission check on output directory
        check_permissions(output_dir, need_write=True)

        cache_dir = config.CACHE_DIR
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Disk space check — estimate ~2x video size for temp files
        video_size_mb = video_path.stat().st_size / (1024 * 1024)
        required_space_mb = max(500, video_size_mb * 2)
        check_disk_space(cache_dir, required_mb=required_space_mb)

        # --- Compute cache key ---
        cache_key = _compute_cache_key(video_path)

        # --- Scene-cut mode: detect + export all scenes, then exit ---
        if args.scene_cut:
            scenes_dir = output_dir / "scenes"
            threshold = args.scene_threshold

            print()
            print("=" * 60)
            print("  ✂  highlight-detect — SCENE CUT MODE")
            print("=" * 60)
            print(f"  Video:       {video_path.name}")
            print(f"  Threshold:   {threshold if threshold else config.SCENE_THRESHOLD} "
                  f"(lower = more cuts)")
            print(f"  Output dir:  {scenes_dir}")
            print(f"  Cache key:   {cache_key}")
            print("=" * 60)
            print()

            t0 = time.time()
            scenes = detect_scenes_full(
                video_path, cache_key, cache_dir, threshold=threshold
            )

            if not scenes:
                print("No scene changes detected. Try lowering --scene-threshold "
                      "(e.g. --scene-threshold 15).")
                sys.exit(0)

            # Print a summary table of all scenes
            print(f"\n{'─' * 55}")
            print(f"  {'#':>4}  {'Start':>8}  {'End':>8}  {'Duration':>10}")
            print(f"{'─' * 55}")
            for s in scenes:
                print(f"  {s['scene_num']:>4}  "
                      f"{_format_time(s['start']):>8}  "
                      f"{_format_time(s['end']):>8}  "
                      f"{s['duration']:>8.1f}s")
            print(f"{'─' * 55}")
            print(f"  Total: {len(scenes)} scenes")

            export_all_scenes(video_path, scenes, scenes_dir)

            print(f"\n⏱  Total time: {time.time() - t0:.1f}s")
            return

        # --- Normal highlight-detect mode ---
        print()
        print("=" * 60)
        print("  🎬  highlight-detect")
        print("=" * 60)
        print(f"  Video:         {video_path.name}")
        print(f"  Clip range:    {args.min_clip_length}s – {args.max_clip_length}s")
        print(f"  Top N:         {args.top_n}")
        print(f"  Export clips:  {'yes' if args.export_clips else 'no'}")
        print(f"  Cache key:     {cache_key}")
        print(f"  Output dir:    {output_dir}")
        print("=" * 60)
        print()

        overall_start = time.time()

        # --- Stage 1: Audio Energy Analysis ---
        print("━" * 50)
        print("📊 Stage 1/4: Audio Energy Analysis")
        print("━" * 50)
        t0 = time.time()
        audio_path = extract_audio(video_path, cache_dir)
        energy_peaks = analyze_energy(audio_path, cache_key, cache_dir)
        print(f"  ⏱  Stage 1 completed in {time.time() - t0:.1f}s\n")

        # --- Stage 2: Scene Change Detection ---
        print("━" * 50)
        print("🎬 Stage 2/4: Scene Change Detection")
        print("━" * 50)
        t0 = time.time()
        scene_boundaries = detect_scenes(video_path, cache_key, cache_dir)
        print(f"  ⏱  Stage 2 completed in {time.time() - t0:.1f}s\n")

        # --- Stage 3: Transcription + Lexical Signal ---
        print("━" * 50)
        print("🎤 Stage 3/4: Transcription (faster-whisper)")
        print("━" * 50)
        t0 = time.time()
        transcript_segments = transcribe_audio(audio_path, cache_key, cache_dir)
        lexical_signal = compute_lexical_signal(transcript_segments)
        print(f"  ⏱  Stage 3 completed in {time.time() - t0:.1f}s\n")

        # --- Stage 4: Segment Scoring ---
        print("━" * 50)
        print("🏆 Stage 4/4: Segment Scoring")
        print("━" * 50)
        t0 = time.time()

        # Determine video duration
        video_duration = _get_video_duration(video_path)
        if video_duration <= 0 and transcript_segments:
            video_duration = transcript_segments[-1]["end"]
        if video_duration <= 0:
            print("✗ Could not determine video duration. Aborting.")
            sys.exit(1)

        print(f"  Video duration: {_format_time(video_duration)} ({video_duration:.0f}s)")

        # Check if video is long enough for the requested clip length
        if video_duration < args.min_clip_length:
            print(f"⚠  Video ({video_duration:.1f}s) is shorter than --min-clip-length "
                  f"({args.min_clip_length}s). Adjusting min to {video_duration:.1f}s.")
            args.min_clip_length = max(0.1, float(video_duration))

        scored = score_windows(
            energy_peaks=energy_peaks,
            scene_boundaries=scene_boundaries,
            lexical_signal=lexical_signal,
            video_duration=video_duration,
            min_clip_length=args.min_clip_length,
            max_clip_length=min(args.max_clip_length, float(video_duration)),
        )

        highlights = deduplicate_windows(scored, top_n=args.top_n)
        print(f"  ⏱  Stage 4 completed in {time.time() - t0:.1f}s\n")

        # --- Output ---
        total_time = time.time() - overall_start
        print(f"✅ Pipeline completed in {total_time:.1f}s total.\n")

        if not highlights:
            print("No highlights found. Try lowering --min-clip-length or "
                  "adjusting weights in config.py.")
            sys.exit(0)

        # Print table
        _print_results_table(highlights, transcript_segments)

        # Write JSON
        json_output = output_dir / "highlights.json"
        json_data = {
            "video": str(video_path),
            "video_duration": video_duration,
            "settings": {
                "min_clip_length": args.min_clip_length,
                "max_clip_length": args.max_clip_length,
                "top_n": args.top_n,
                "audio_weight": config.AUDIO_WEIGHT,
                "scene_weight": config.SCENE_WEIGHT,
                "lexical_weight": config.LEXICAL_WEIGHT,
                "whisper_model": config.WHISPER_MODEL,
            },
            "highlights": [],
        }

        for i, h in enumerate(highlights, 1):
            transcript_text = _get_transcript_for_window(
                transcript_segments, h["start"], h["end"], max_chars=5000
            )
            json_data["highlights"].append({
                "rank": i,
                "start": h["start"],
                "end": h["end"],
                "duration": h["duration"],
                "score": h["score"],
                "audio_score": h["audio_score"],
                "scene_score": h["scene_score"],
                "lexical_score": h["lexical_score"],
                "transcript": transcript_text,
            })

        with open(json_output, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        print(f"📄 JSON results written to {json_output}")

        # Export clips if requested
        if args.export_clips:
            _export_clips(highlights, video_path, output_dir)

        print("\nDone! Review the clips and adjust weights in "
              "highlight_detect/config.py to iterate.")

    except ClipSenseError as e:
        handle_exception(e)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠  Interrupted by user.")
        sys.exit(130)
    except Exception as e:
        handle_exception(e)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
transcribe.py — Stage 3: Speech-to-text transcription and lexical signal.

Uses faster-whisper (CTranslate2-based) to transcribe audio, then computes
a lexical signal based on hook words, exclamations, and question phrasing.

Public functions:
    transcribe_audio(audio_path, cache_key, cache_dir) -> list[dict]
    compute_lexical_signal(transcript_segments) -> list[tuple[float, float, float]]
"""

import json
import re
from pathlib import Path

from faster_whisper import WhisperModel

from . import config
from .error_handler import ModelCorruptError, ClipSenseError, get_logger


def transcribe_audio(
    audio_path: str | Path,
    cache_key: str,
    cache_dir: Path,
) -> list[dict]:
    """Transcribe audio using faster-whisper and return timestamped segments.

    This is typically the slowest stage in the pipeline, so results are
    cached aggressively to disk.

    Args:
        audio_path: Path to the .wav audio file.
        cache_key: Unique key for caching (derived from video file identity).
        cache_dir: Directory to store cached results.

    Returns:
        List of segment dicts, each with keys: start (float), end (float), text (str).
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"transcript_{cache_key}.json"

    # Check cache — this is the big one we really want to avoid re-running
    if cache_file.exists():
        print("  ✓ Transcript found in cache, loading (skipping transcription)...")
        with open(cache_file, "r") as f:
            cached = json.load(f)
        return cached["segments"]

    model_name = config.WHISPER_MODEL
    compute_type = config.WHISPER_COMPUTE_TYPE
    device = config.WHISPER_DEVICE

    print(f"  ⏳ Loading faster-whisper model '{model_name}' "
          f"(compute_type={compute_type}, device={device})...")

    # Load model with defensive error handling
    try:
        model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
        )
    except (FileNotFoundError, OSError) as e:
        raise ModelCorruptError(
            detail=f"Failed to load model '{model_name}': {e}",
        )
    except RuntimeError as e:
        logger = get_logger()
        logger.error("Transcription engine failed to initialize: %s", e, exc_info=True)
        raise ClipSenseError(
            user_message=(
                f"\u274c Transcription engine failed to initialize.\n"
                f"   Model: {model_name}, compute_type: {compute_type}\n"
                f"   Error: {e}\n"
                f"\n"
                f"   Check the log file for details:\n"
                f"   ~/Library/Logs/ClipSense/clipsense.log"
            ),
            technical_detail=f"WhisperModel RuntimeError: {e}",
        )
    except Exception as e:
        logger = get_logger()
        logger.error("Unexpected error loading model: %s", e, exc_info=True)
        raise ClipSenseError(
            user_message=(
                f"\u274c Could not load the transcription model.\n"
                f"   Error: {e}\n"
                f"   Try reinstalling ClipSense or check the log file:\n"
                f"   ~/Library/Logs/ClipSense/clipsense.log"
            ),
            technical_detail=f"Model load error: {e}",
        )

    print(f"  \u23f3 Transcribing audio (this may take a while on long videos)...")

    # Transcribe with defensive error handling
    try:
        # faster-whisper returns (segments_iterator, info)
        segments_iter, info = model.transcribe(
            str(audio_path),
            beam_size=5,
            language=None,  # auto-detect language
        )

        detected_language = info.language

        # Consume the iterator and convert to our standard dict format
        segments = []
        for seg in segments_iter:
            segments.append({
                "start": float(seg.start),
                "end": float(seg.end),
                "text": seg.text.strip(),
            })
    except Exception as e:
        logger = get_logger()
        logger.error("Transcription failed: %s", e, exc_info=True)
        raise ClipSenseError(
            user_message=(
                f"\u274c Transcription failed while processing the audio.\n"
                f"   Error: {e}\n"
                f"   The audio file may be corrupted or in an unsupported format.\n"
                f"   Check the log file for details:\n"
                f"   ~/Library/Logs/ClipSense/clipsense.log"
            ),
            technical_detail=f"Transcription error: {e}",
        )




    total_words = sum(len(s["text"].split()) for s in segments)
    duration = segments[-1]["end"] if segments else 0
    print(f"  ✓ Transcription complete: {len(segments)} segments, "
          f"~{total_words} words, {duration:.0f}s of speech. "
          f"(detected language: {detected_language})")

    # Cache
    cache_data = {
        "model": model_name,
        "compute_type": compute_type,
        "language": detected_language or "unknown",
        "segments": segments,
    }
    with open(cache_file, "w") as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)

    return segments


def compute_lexical_signal(
    transcript_segments: list[dict],
) -> list[tuple[float, float, float]]:
    """Score each transcript segment for 'highlight-worthy' language.

    Scoring criteria per segment:
        - Hook words/phrases: +1.0 per match found in config.HOOK_WORDS
        - Exclamation marks: +0.5 per '!'
        - Question marks: +0.3 per '?'

    Scores are normalized to 0–1 across all segments.

    Args:
        transcript_segments: List of {start, end, text} dicts from transcribe_audio().

    Returns:
        List of (start_sec, end_sec, lexical_score) tuples.
        Scores are normalized 0–1 (0 = no signal, 1 = max signal in this video).
    """
    if not transcript_segments:
        return []

    hook_words = config.HOOK_WORDS

    raw_scores = []
    for seg in transcript_segments:
        text = seg["text"].lower()
        score = 0.0

        # Hook words — check for each phrase
        for word in hook_words:
            # Use word boundary matching for single words,
            # simple substring matching for multi-word phrases
            if " " in word:
                if word in text:
                    score += 1.0
            else:
                # Match as whole word
                pattern = r'\b' + re.escape(word) + r'\b'
                matches = re.findall(pattern, text)
                score += len(matches) * 1.0

        # Exclamation marks
        score += text.count("!") * 0.5

        # Question marks
        score += text.count("?") * 0.3

        raw_scores.append(score)

    # Normalize to 0–1
    max_score = max(raw_scores) if raw_scores else 1.0
    if max_score > 0:
        normalized = [s / max_score for s in raw_scores]
    else:
        normalized = [0.0] * len(raw_scores)

    result = []
    for seg, norm_score in zip(transcript_segments, normalized):
        result.append((seg["start"], seg["end"], norm_score))

    print(f"  ✓ Lexical signal computed: "
          f"{sum(1 for s in normalized if s > 0)}/{len(normalized)} segments "
          f"have hook-word / exclamation signal.")

    return result

"""
transcribe.py — Stage 3: Speech-to-text transcription and lexical signal.

Uses OpenAI's Whisper (local, offline) to transcribe audio, then computes
a lexical signal based on hook words, exclamations, and question phrasing.

Public functions:
    transcribe_audio(audio_path, cache_key, cache_dir) -> list[dict]
    compute_lexical_signal(transcript_segments) -> list[tuple[float, float, float]]
"""

import json
import re
from pathlib import Path

import whisper

from . import config


def transcribe_audio(
    audio_path: str | Path,
    cache_key: str,
    cache_dir: Path,
) -> list[dict]:
    """Transcribe audio using Whisper and return timestamped segments.

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
        print("  ✓ Transcript found in cache, loading (skipping Whisper)...")
        with open(cache_file, "r") as f:
            cached = json.load(f)
        return cached["segments"]

    model_name = config.WHISPER_MODEL
    print(f"  ⏳ Loading Whisper model '{model_name}'...")
    model = whisper.load_model(model_name)

    print(f"  ⏳ Transcribing audio (this may take a while on long videos)...")
    result = model.transcribe(
        str(audio_path),
        verbose=False,   # suppress Whisper's own progress output
        language=None,    # auto-detect language
    )

    # Extract segments
    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": float(seg["start"]),
            "end": float(seg["end"]),
            "text": seg["text"].strip(),
        })

    total_words = sum(len(s["text"].split()) for s in segments)
    duration = segments[-1]["end"] if segments else 0
    print(f"  ✓ Transcription complete: {len(segments)} segments, "
          f"~{total_words} words, {duration:.0f}s of speech.")

    # Cache
    cache_data = {
        "model": model_name,
        "language": result.get("language", "unknown"),
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

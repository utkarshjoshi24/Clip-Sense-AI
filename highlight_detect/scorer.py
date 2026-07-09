"""
scorer.py — Stage 4: Sliding-window segment scoring and deduplication.

Takes the outputs of stages 1–3 (energy peaks, scene boundaries, lexical signal)
and computes a composite score for candidate highlight windows. Deduplicates
overlapping windows and returns the top N picks.

Public functions:
    score_windows(...) -> list[dict]
    deduplicate_windows(scored_windows, top_n) -> list[dict]
"""

from . import config


def _audio_score_for_window(
    energy_peaks: list[tuple[float, float]],
    window_start: float,
    window_end: float,
) -> float:
    """Compute the audio energy sub-score for a candidate window.

    Returns the maximum energy peak score found within the window bounds.
    If no peaks fall in the window, returns 0.
    """
    max_score = 0.0
    for timestamp, score in energy_peaks:
        if window_start <= timestamp <= window_end:
            max_score = max(max_score, score)
    return max_score


def _scene_score_for_window(
    scene_boundaries: list[float],
    window_start: float,
    window_end: float,
) -> float:
    """Compute the scene-boundary proximity sub-score for a candidate window.

    Rewards windows whose start and end are close to a natural scene boundary.
    Score is the average of start-proximity and end-proximity, each ranging 0–1.

    A distance of 0s from a boundary = 1.0 score.
    A distance >= SCENE_PROXIMITY_SEC = 0.0 score.
    """
    if not scene_boundaries:
        return 0.0

    max_dist = config.SCENE_PROXIMITY_SEC

    # Find closest boundary to window start
    min_start_dist = min(abs(window_start - b) for b in scene_boundaries)
    start_score = max(0.0, 1.0 - min_start_dist / max_dist)

    # Find closest boundary to window end
    min_end_dist = min(abs(window_end - b) for b in scene_boundaries)
    end_score = max(0.0, 1.0 - min_end_dist / max_dist)

    return (start_score + end_score) / 2.0


def _lexical_score_for_window(
    lexical_signal: list[tuple[float, float, float]],
    window_start: float,
    window_end: float,
) -> float:
    """Compute the lexical signal density sub-score for a candidate window.

    Returns the average lexical score of all transcript segments that overlap
    with the window. If no segments overlap, returns 0.
    """
    if not lexical_signal:
        return 0.0

    scores = []
    for seg_start, seg_end, seg_score in lexical_signal:
        # Check if segment overlaps with window
        if seg_end >= window_start and seg_start <= window_end:
            scores.append(seg_score)

    if not scores:
        return 0.0

    return sum(scores) / len(scores)


def score_windows(
    energy_peaks: list[tuple[float, float]],
    scene_boundaries: list[float],
    lexical_signal: list[tuple[float, float, float]],
    video_duration: float,
    min_clip_length: int,
    max_clip_length: int,
) -> list[dict]:
    """Score all candidate highlight windows across the video.

    Slides windows of varying lengths across the video and computes a
    composite score for each using the three sub-signals.

    Args:
        energy_peaks: List of (timestamp, energy_score) from audio analysis.
        scene_boundaries: List of scene-boundary timestamps.
        lexical_signal: List of (start, end, lexical_score) from transcription.
        video_duration: Total video duration in seconds.
        min_clip_length: Minimum clip length in seconds.
        max_clip_length: Maximum clip length in seconds.

    Returns:
        List of scored window dicts with keys:
            start, end, duration, score, audio_score, scene_score, lexical_score
    """
    step = config.SCORING_STEP_SEC
    length_step = config.CLIP_LENGTH_STEP_SEC

    # Generate clip lengths to test
    clip_lengths = list(range(min_clip_length, max_clip_length + 1, length_step))
    if max_clip_length not in clip_lengths:
        clip_lengths.append(max_clip_length)

    total_windows = 0
    for clip_len in clip_lengths:
        num_positions = max(1, int((video_duration - clip_len) / step) + 1)
        total_windows += num_positions

    print(f"  ⏳ Scoring {total_windows} candidate windows "
          f"({len(clip_lengths)} clip lengths × sliding positions)...")

    scored = []
    for clip_len in clip_lengths:
        start = 0.0
        while start + clip_len <= video_duration:
            end = start + clip_len

            # Compute sub-scores
            a_score = _audio_score_for_window(energy_peaks, start, end)
            s_score = _scene_score_for_window(scene_boundaries, start, end)
            l_score = _lexical_score_for_window(lexical_signal, start, end)

            # Weighted composite
            composite = (
                config.AUDIO_WEIGHT * a_score
                + config.SCENE_WEIGHT * s_score
                + config.LEXICAL_WEIGHT * l_score
            )

            scored.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "duration": round(clip_len, 2),
                "score": round(composite, 4),
                "audio_score": round(a_score, 4),
                "scene_score": round(s_score, 4),
                "lexical_score": round(l_score, 4),
            })

            start += step

    # Sort by score descending
    scored.sort(key=lambda w: w["score"], reverse=True)

    print(f"  ✓ Scored {len(scored)} windows. "
          f"Top score: {scored[0]['score']:.4f}, "
          f"Bottom score: {scored[-1]['score']:.4f}" if scored else "  ✓ No windows scored.")

    return scored


def _overlap_fraction(w1: dict, w2: dict) -> float:
    """Compute the overlap fraction between two windows.

    Returns the overlap duration divided by the shorter window's duration.
    """
    overlap_start = max(w1["start"], w2["start"])
    overlap_end = min(w1["end"], w2["end"])
    overlap = max(0, overlap_end - overlap_start)

    shorter_duration = min(w1["duration"], w2["duration"])
    if shorter_duration <= 0:
        return 0.0

    return overlap / shorter_duration


def deduplicate_windows(
    scored_windows: list[dict],
    top_n: int,
) -> list[dict]:
    """Greedily select top-N non-overlapping windows (non-maximum suppression).

    Starting from the highest-scored window, greedily adds windows to the
    result set, skipping any that overlap with an already-selected window
    by more than OVERLAP_THRESHOLD.

    Args:
        scored_windows: List of scored window dicts, sorted by score descending.
        top_n: Number of windows to return.

    Returns:
        Top N non-overlapping windows, sorted by score descending.
    """
    if not scored_windows:
        return []

    selected = []
    for candidate in scored_windows:
        if len(selected) >= top_n:
            break

        # Check overlap with all already-selected windows
        overlaps = False
        for existing in selected:
            if _overlap_fraction(candidate, existing) > config.OVERLAP_THRESHOLD:
                overlaps = True
                break

        if not overlaps:
            selected.append(candidate)

    print(f"  ✓ Selected top {len(selected)} non-overlapping highlight windows.")
    return selected

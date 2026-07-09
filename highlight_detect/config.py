"""
config.py — Central configuration for highlight-detect.

All scoring weights, thresholds, and tunable parameters live here.
Edit these values to iterate on scoring quality without touching any other file.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Root of the project (directory containing this package)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Hook-words file — one word/phrase per line
HOOK_WORDS_FILE = PROJECT_ROOT / "hook_words.txt"

# Cache directory for intermediate results (audio energy, transcript, scenes)
CACHE_DIR = PROJECT_ROOT / ".highlight_cache"

# Default output directory for results and exported clips
OUTPUT_DIR = PROJECT_ROOT / "output"

# ---------------------------------------------------------------------------
# Audio Energy Analysis (Stage 1)
# ---------------------------------------------------------------------------

# RMS energy window size in seconds
RMS_WINDOW_SEC = 0.5

# Savitzky-Golay smoothing filter — window length (must be odd)
ENERGY_SMOOTHING_WINDOW = 15

# Savitzky-Golay polynomial order
ENERGY_SMOOTHING_POLY = 3

# scipy.signal.find_peaks prominence threshold (0–1 after normalization)
PEAK_PROMINENCE = 0.3

# Minimum distance between peaks in number of frames
PEAK_DISTANCE = 10

# ---------------------------------------------------------------------------
# Scene Detection (Stage 2)
# ---------------------------------------------------------------------------

# ContentDetector threshold — lower = more sensitive to scene changes
SCENE_THRESHOLD = 15.0

# ---------------------------------------------------------------------------
# Transcription (Stage 3)
# ---------------------------------------------------------------------------

# Whisper model size: "tiny", "base", "small", "medium", "large"
# Use "base" for fast iteration, bump to "small" once scoring is tuned
WHISPER_MODEL = "base"

# ---------------------------------------------------------------------------
# Scoring (Stage 4)
# ---------------------------------------------------------------------------

# Composite score weights — must sum to 1.0
AUDIO_WEIGHT = 0.4
SCENE_WEIGHT = 0.3
LEXICAL_WEIGHT = 0.3

# Max distance (seconds) from a scene boundary to receive proximity credit.
# Windows whose start/end is further than this from any boundary get 0 scene score.
SCENE_PROXIMITY_SEC = 5.0

# Sliding window step size in seconds
SCORING_STEP_SEC = 15

# Clip length step — we test window sizes from min_clip to max_clip in these increments
CLIP_LENGTH_STEP_SEC = 30

# Overlap threshold for deduplication — if two windows overlap by more than
# this fraction of the shorter window's length, keep only the higher-scored one.
OVERLAP_THRESHOLD = 0.5

# ---------------------------------------------------------------------------
# Hook Words
# ---------------------------------------------------------------------------

def load_hook_words(path: Path = HOOK_WORDS_FILE) -> list[str]:
    """Load hook words/phrases from a text file, one per line.
    
    Lines that are empty or start with '#' are ignored.
    All entries are lowercased for case-insensitive matching.
    """
    if not path.exists():
        print(f"⚠  Hook-words file not found at {path}, using empty list.")
        return []
    
    words = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                words.append(line.lower())
    return words


# Load hook words at import time so other modules can just use config.HOOK_WORDS
HOOK_WORDS = load_hook_words()

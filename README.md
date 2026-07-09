# highlight-detect

A standalone Python CLI tool that analyzes a long-form video file and outputs a ranked list of candidate highlight clips. Built for research and validation — run it against your own footage, watch the picks, tune the scoring weights, repeat.

## Prerequisites

- **Python 3.10+**
- **ffmpeg** (must be installed separately and on your PATH)
  ```bash
  # macOS
  brew install ffmpeg

  # Ubuntu/Debian
  sudo apt install ffmpeg

  # Windows (with Chocolatey)
  choco install ffmpeg
  ```

## Setup

```bash
# Clone or navigate to the project
cd Clip-Sense

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate   # macOS/Linux
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

> **Note**: The first run will download the Whisper model (~140 MB for "base"). This is a one-time download.

## Usage

### Basic usage
```bash
python -m highlight_detect video.mp4
```

### With options
```bash
python -m highlight_detect video.mp4 \
  --min-clip-length 30 \
  --max-clip-length 300 \
  --top-n 5
```

### Export clips as separate mp4 files
```bash
python -m highlight_detect video.mp4 --export-clips --output-dir ./my_clips
```

### All options
```
python -m highlight_detect --help

positional arguments:
  video                 Path to the input video file (mp4/mov)

options:
  --min-clip-length N   Minimum clip length in seconds (default: 60)
  --max-clip-length N   Maximum clip length in seconds (default: 600)
  --top-n N             Number of candidate clips to return (default: 10)
  --export-clips        Export each clip as a separate mp4 file
  --output-dir DIR      Directory for output files (default: ./output)
```

## Output Columns Explained

When the tool finishes, it prints a table like this:

| Column | Meaning |
|--------|---------|
| **Rank** | Position in the ranked list (1 = best candidate) |
| **Start** | Start timestamp of the candidate clip (HH:MM:SS) |
| **End** | End timestamp of the candidate clip |
| **Duration** | Length of the clip |
| **Score** | Composite score (0–1) — weighted combination of the three sub-scores below |
| **Audio** | Audio energy sub-score (0–1). High = loud/energetic moments (music hits, laughter, applause) |
| **Scene** | Scene-boundary proximity sub-score (0–1). High = clip starts/ends near a natural cut point rather than mid-sentence |
| **Lexical** | Transcript hook-word sub-score (0–1). High = speaker uses attention-grabbing language ("crazy", "the secret", etc.) |
| **Transcript Preview** | First ~120 characters of what's being said in the clip, so you can quickly judge relevance |

## How It Works

The pipeline runs 4 stages:

1. **Audio Energy** — Extracts audio, computes RMS energy curve, finds peaks (loud/energetic moments).
2. **Scene Detection** — Uses PySceneDetect to find natural cut points in the video.
3. **Transcription** — Runs Whisper to get timestamped text, then scores each segment for hook words and exclamatory language.
4. **Scoring** — Slides windows across the video and scores each based on a weighted combination of audio energy, scene-boundary proximity, and lexical signal density. Deduplicates overlapping picks.

## Tuning the Scoring

All weights and thresholds live in [`highlight_detect/config.py`](highlight_detect/config.py). The key ones to tune:

```python
# Composite score weights (must sum to 1.0)
AUDIO_WEIGHT = 0.4      # How much to weight loud/energetic moments
SCENE_WEIGHT = 0.3      # How much to reward natural cut points
LEXICAL_WEIGHT = 0.3    # How much to reward hook-word-rich speech

# Peak detection sensitivity
PEAK_PROMINENCE = 0.3   # Lower = more peaks detected

# Scene boundary proximity
SCENE_PROXIMITY_SEC = 5.0  # How close (seconds) to a cut point to get credit
```

Hook words live in [`hook_words.txt`](hook_words.txt) — edit this file to add/remove phrases without touching code.

## Caching

Intermediate results (audio extraction, energy curve, scene boundaries, transcript) are cached in `.highlight_cache/` keyed by your video file's identity. This means:

- **Re-running with different scoring weights** skips all the slow stages (especially Whisper transcription) and only re-computes the scoring. This is the fast-iteration loop.
- **Running on a different video** computes everything from scratch.
- **Delete `.highlight_cache/`** to force a full re-run.

## Project Structure

```
Clip-Sense/
├── highlight_detect/
│   ├── __init__.py          # Package marker
│   ├── __main__.py          # python -m entry point
│   ├── cli.py               # Argument parsing + pipeline orchestration
│   ├── config.py            # All tunable weights and thresholds
│   ├── audio_energy.py      # Stage 1: Audio extraction + RMS energy
│   ├── scene_detect.py      # Stage 2: Scene change detection
│   ├── transcribe.py        # Stage 3: Whisper transcription + lexical signal
│   └── scorer.py            # Stage 4: Sliding-window scoring + dedup
├── hook_words.txt           # Editable hook-word list
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

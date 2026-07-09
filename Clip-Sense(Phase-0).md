# Phase 0 — Highlight Detection CLI (Validation Prompt)

Goal of this phase: prove the core idea works on real footage *before* you build any web app around it. This should take a few hours to a day, not weeks. If the output clips aren't actually good on your own videos, stop and iterate on the scoring logic — don't move to Phase 1 yet.

Paste the prompt below into Antigravity (or Claude Code — either works fine for this phase since it's just a Python CLI, no infra).

---

## Antigravity / Claude Code prompt

```
Build a standalone Python CLI tool called "highlight-detect" that analyzes a long-form
video file and outputs a ranked list of candidate highlight clips. This is a research/
validation script, not a production app — prioritize correctness and readability over
architecture. No web framework, no database, no auth. Just a script I can run against
my own video files and inspect the output.

INPUT:
- A single video file path (mp4/mov), passed as a CLI argument.
- Optional flags: --min-clip-length (default 60s), --max-clip-length (default 600s),
  --top-n (default 10, how many candidate clips to return).

PIPELINE STAGES (implement each as a separate, independently callable function so I
can test and tune them individually):

1. AUDIO ENERGY ANALYSIS
   - Extract audio from the video using ffmpeg (via subprocess or ffmpeg-python).
   - Use librosa to compute short-time energy (RMS) and/or spectral flux over the
     full audio track in small windows (e.g., 0.5s).
   - Normalize and smooth the resulting energy curve.
   - Identify local peaks (energy spikes) using scipy.signal.find_peaks, with
     configurable prominence threshold.
   - Output: a list of (timestamp, energy_score) pairs.

2. SCENE CHANGE DETECTION
   - Use PySceneDetect (content-aware detector) to find timestamps of scene/shot
     changes in the video.
   - Output: a list of scene-boundary timestamps.

3. SPEECH-TO-TEXT TRANSCRIPTION
   - Run local Whisper (use the "base" or "small" model to keep this fast for
     validation — don't default to "large" for a quick test loop) on the extracted
     audio.
   - Output: a timestamped transcript (list of segments with start, end, text).
   - From the transcript, compute a simple lexical signal per time window: flag
     segments containing exclamation-heavy phrasing, question phrasing, or a
     manually-defined list of "hook" words/phrases (e.g. "crazy", "insane", "wait",
     "the secret", "nobody tells you") — make this word list a separate config file
     so I can edit it without touching code.

4. SEGMENT SCORING
   - Slide a window across the video (respecting --min-clip-length and
     --max-clip-length) and compute a composite score for each candidate window:
     - audio energy peak within the window (weight configurable, default 0.4)
     - proximity to a scene-change boundary at the window's start/end
       (weight configurable, default 0.3 — reward windows that start/end near a
       natural cut point rather than mid-sentence/mid-action)
     - lexical/transcript signal density within the window (weight configurable,
       default 0.3)
   - Merge/deduplicate overlapping high-scoring windows (if two windows overlap
     more than 50%, keep only the higher-scoring one).
   - Return the top N non-overlapping windows sorted by score.

5. OUTPUT
   - Print a human-readable table to the terminal: rank, start time, end time,
     duration, composite score, and the transcript text for that window (so I can
     immediately judge if the pick makes sense).
   - Also write a JSON file with the same data (for later use by the web app).
   - Optionally (flag --export-clips), use ffmpeg to actually cut out each
     candidate clip as a separate mp4 file into an /output folder, so I can watch
     them directly instead of just trusting the scores.

CODE STRUCTURE:
- /highlight_detect
  - audio_energy.py
  - scene_detect.py
  - transcribe.py
  - scorer.py
  - config.py (weights, thresholds, hook-word list — all in one place, easy to tune)
  - cli.py (entry point, argument parsing, orchestrates the pipeline)
- requirements.txt
- README.md with setup instructions (including that ffmpeg must be installed
  separately) and example usage command

IMPORTANT:
- Each stage should print progress to the terminal (e.g. "Extracting audio...",
  "Running scene detection...", "Transcribing with Whisper...") since this will
  take a while on longer videos and I need to know it's not stuck.
- Cache intermediate results (transcript, audio energy curve) to disk keyed by
  video filename hash, so if I re-run with different scoring weights I don't have
  to re-run Whisper transcription every time — that's the slowest step.
- Keep the scoring weights and thresholds easy to tweak in config.py since I'll be
  iterating on these numbers a lot based on how good the picks actually look.

After building this, walk me through how to run it on a sample video and explain
what each output column means.
```

---

## How to actually validate it (don't skip this part)

1. Run it on 2-3 of your own past long-form recordings — ideally ones where you already know, from having manually edited them, which moments were the best clips. That's your ground truth.
2. Check: does the tool's top-5 list roughly match what you'd have picked manually? It won't be perfect — you're checking for "directionally right," not "perfect."
3. Use the `--export-clips` flag to actually watch the cut clips, not just read the scores. A high score with an awkward mid-sentence cut is a real failure mode — that's exactly what the scene-change weighting is meant to prevent, so this is where you'll notice if that weight needs adjusting.
4. Tune the weights in `config.py` based on what you see. This tuning loop — run, watch, adjust weights, re-run — is the actual "ML work" of this project, and it's also your strongest interview story ("I iterated on the scoring weights based on manually validating against my own edited footage").

Once the top clips are consistently reasonable across a few different source videos, you're done with Phase 0 — come back and I'll help you kick off Phase 1.

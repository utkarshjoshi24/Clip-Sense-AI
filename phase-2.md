# ClipSense macOS Resolve Plugin — Hardened, Size-Efficient Version

## Honest framing first

"Perfectly works on every system, never breaks" isn't a real engineering target — no shipped software hits that, including Resolve and Premiere themselves. What's actually achievable, and what this prompt targets, is:

- **Works on both Mac architectures** (Apple Silicon and Intel) — this is the most common real-world "it broke on their machine" cause, not some exotic edge case.
- **Fails safely instead of crashing** — if something's wrong (missing permission, corrupted download, incompatible Resolve version), the user sees a clear message, not a silent crash or a spinning wheel forever.
- **Small enough to not be its own problem** — swapping the transcription engine gets you from a 1-2GB+ installer down to realistically 150-400MB depending on model size chosen.

That's the honest, buildable version of what you're asking for. Here's the architecture change and the prompt.

## The key change: faster-whisper instead of openai-whisper

| | openai-whisper (previous plan) | faster-whisper |
|---|---|---|
| Backend | PyTorch | CTranslate2 (C++ inference engine) |
| Typical bundle size | 1-2GB+ (PyTorch alone is 600MB+) | 150-400MB depending on model size |
| Speed on CPU | Slower | Meaningfully faster (this library exists specifically to fix Whisper's CPU speed) |
| Dependency fragility | High — PyTorch has notoriously finicky bundling behavior with PyInstaller | Low — CTranslate2 is a much smaller, more bundler-friendly C++ library |
| Model quantization | Possible but clunky | Built-in (int8 quantized models are standard usage, not a hack) |

This isn't a tradeoff against quality — faster-whisper produces the same transcription output as openai-whisper (it's a reimplementation of the same models), just via a lighter, faster, more bundle-friendly engine. There's no real reason to still be on openai-whisper for this use case.

---

## Antigravity prompt

```
Repo: https://github.com/utkarshjoshi24/Clip-Sense-AI

You are hardening and rebuilding the macOS DaVinci Resolve plugin installer for
ClipSense to be reliable across both Mac architectures (Apple Silicon and Intel),
fail safely instead of crashing, and be meaningfully smaller than a PyTorch-based
build. This replaces the previous plugin bundling approach.

STEP 1 — SWAP THE TRANSCRIPTION ENGINE
- Replace openai-whisper (PyTorch-based) with faster-whisper (CTranslate2-based)
  throughout /highlight_detect/transcribe.py. The output format (timestamped
  segments) should remain the same so nothing downstream (scorer.py, the API,
  the frontend) needs to change.
- Use a quantized model (int8) by default — specifically the "base" or "small"
  faster-whisper model, not "medium" or "large", to keep the bundle size and
  inference time reasonable for a plugin that needs to feel responsive inside an
  editing workflow. Make the model size configurable, defaulting to the smallest
  size that still gives acceptably accurate transcripts for hook-word detection
  (perfect word-for-word accuracy isn't the goal here, catching emphasis/keyword
  signal is).
- Confirm this change doesn't require PyTorch as a dependency anywhere in the
  pipeline anymore — audit requirements.txt and remove torch/torchaudio if no
  longer needed by any other component.

STEP 2 — UNIVERSAL BUILD (Apple Silicon + Intel)
- Build the standalone Python bundle (via PyInstaller or your chosen bundler) as
  a universal2 binary, or alternatively build two separate architecture-specific
  bundles (one for arm64, one for x86_64) and have the installer detect the
  target Mac's architecture and install the correct one. Do not ship an
  Apple-Silicon-only or Intel-only build as if it's universal — this is the most
  common real-world cause of "works on my machine, breaks on theirs" for Mac
  software, since Apple Silicon and Intel Macs are both common in the wild.
- Bundle a universal (or per-architecture) static ffmpeg binary to match.
- Add an explicit architecture/compatibility check early in the plugin's startup
  that fails with a clear, human-readable error message if something's wrong,
  rather than crashing deep in the pipeline with a cryptic stack trace.

STEP 3 — FAIL SAFELY, DON'T CRASH
Wrap every external dependency point in defensive error handling with clear
user-facing messages, specifically:
- Missing/corrupted DaVinci Resolve installation or incompatible Resolve version
  → clear message naming the required version range, not a silent failure.
- Bundled ffmpeg or model files missing/corrupted (e.g. from an interrupted
  install) → detect this at startup and prompt the user to reinstall, rather
  than crashing partway through processing a clip.
- Insufficient disk space for temporary processing files → check available space
  before starting a job and warn the user with the actual space needed, rather
  than failing midway.
- Unsupported input video (corrupt file, unusual codec ffmpeg can't handle)
  → catch ffmpeg errors explicitly and surface a plain-language message
  ("this video's format couldn't be read") instead of letting a raw subprocess
  error surface to the user.
- macOS permission issues (e.g. Resolve or the script lacking file access
  permission under System Settings > Privacy) → detect permission-denied errors
  specifically and tell the user exactly which permission to grant, since this
  is a very common real-world failure mode on modern macOS and is otherwise
  confusing to debug.
- Any unhandled exception in the plugin should be caught at the top level and
  logged to a file in a predictable location (e.g. ~/Library/Logs/ClipSense/)
  with a timestamp, rather than crashing Resolve's scripting console silently —
  the user should always end up with a readable error message AND a log file
  to send you if they report a bug.

STEP 4 — CROSS-MACHINE VALIDATION (this is not optional)
- Set up a GitHub Actions workflow that builds and smoke-tests the installer on
  both macos-13 (Intel runner) and macos-14 (Apple Silicon runner), confirming
  on each: the installer completes without error, the plugin appears in Resolve's
  script menu (if Resolve can be installed in CI — if not, at minimum confirm the
  bundled interpreter runs and can execute the pipeline standalone), and a sample
  short video can be processed end-to-end without crashing.
- This CI matrix is what actually earns you the "works on every system" claim —
  without automated testing on both architectures, that claim is just hope.
  Report back the CI results, not just "should work."

STEP 5 — INSTALLER PACKAGING (as before, updated for the new bundle)
- Package via pkgbuild/productbuild as a single .pkg installer.
- Report the final installer size for each architecture build. Flag clearly if
  either exceeds 500MB, since faster-whisper's whole point was avoiding that.
- Include an uninstall script/instructions, since a plugin that's hard to cleanly
  remove is its own kind of "breaks the user's system."

Build and validate in this order: engine swap first (confirm faster-whisper
produces equivalent transcript quality to the previous openai-whisper output on
a test video before proceeding), then the universal build, then the defensive
error handling, then the CI validation matrix, then final packaging. Do not skip
the CI matrix step even though it's the most tedious one — it's the actual
mechanism that prevents "works on my Mac, breaks on theirs."
```

---

## What "size efficient" actually looks like after this

Rough expected installer size with faster-whisper + a "base" or "small" quantized model + bundled ffmpeg: **150-400MB**, versus 1-2GB+ with the PyTorch-based approach. That's a real, structural improvement, not a compression trick — it comes from removing a dependency you didn't actually need for this use case.

## What "never crashes" actually requires (ongoing, not one-time)

The defensive error handling in Step 3 covers the failure modes you can predict. The CI matrix in Step 4 catches architecture-specific breakage before users hit it. But the honest last piece is: once real users are running this on machines you don't control, you'll find failure modes you didn't predict. The log file setup in Step 3 (`~/Library/Logs/ClipSense/`) is what turns "it crashed and I have no idea why" into a bug report you can actually act on — that's the realistic version of "never breaks": not zero bugs, but every failure is diagnosable instead of silent.

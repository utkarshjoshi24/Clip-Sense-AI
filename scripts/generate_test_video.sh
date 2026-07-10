#!/usr/bin/env bash
# generate_test_video.sh — Generate a short test video with speech for CI.
#
# Creates a 10-second test video with:
#   - Solid color video with text overlay
#   - Synthesized speech-like audio (sine wave tones)
#
# Usage:
#   bash scripts/generate_test_video.sh [output_path]
#
# Default output: test_fixtures/test_video.mp4

set -euo pipefail

OUTPUT="${1:-test_fixtures/test_video.mp4}"
OUTPUT_DIR="$(dirname "$OUTPUT")"

mkdir -p "$OUTPUT_DIR"

echo "🎬 Generating test video: $OUTPUT"

# Generate a 10-second video with:
# - Color bars as video source
# - Sine wave audio that mimics speech frequency range (300Hz, 800Hz, 1200Hz)
# - Duration: 10 seconds
ffmpeg -y \
    -f lavfi -i "smptebars=duration=10:size=640x360:rate=30" \
    -f lavfi -i "sine=frequency=300:duration=3,apad=pad_dur=1[a1]; \
                 sine=frequency=800:duration=3[a2]; \
                 sine=frequency=1200:duration=3,apad=pad_dur=0[a3]; \
                 [a1][a2]concat=n=2:v=0:a=1[ab]; \
                 [ab][a3]concat=n=2:v=0:a=1" \
    -c:v libx264 -preset ultrafast -pix_fmt yuv420p \
    -c:a aac -b:a 64k \
    -t 10 \
    -shortest \
    "$OUTPUT" 2>/dev/null

if [[ $? -eq 0 ]] && [[ -f "$OUTPUT" ]]; then
    SIZE="$(du -h "$OUTPUT" | cut -f1)"
    echo "✓ Test video generated: $OUTPUT ($SIZE)"
else
    echo "✗ Failed to generate test video."
    echo "  Trying simpler fallback..."
    
    # Simpler fallback — just color + sine tone
    ffmpeg -y \
        -f lavfi -i "color=c=blue:s=640x360:d=10:r=30" \
        -f lavfi -i "sine=frequency=440:duration=10" \
        -c:v libx264 -preset ultrafast -pix_fmt yuv420p \
        -c:a aac -b:a 64k \
        -shortest \
        "$OUTPUT" 2>/dev/null
    
    if [[ -f "$OUTPUT" ]]; then
        SIZE="$(du -h "$OUTPUT" | cut -f1)"
        echo "✓ Test video generated (fallback): $OUTPUT ($SIZE)"
    else
        echo "✗ Could not generate test video. Is ffmpeg installed?"
        exit 1
    fi
fi

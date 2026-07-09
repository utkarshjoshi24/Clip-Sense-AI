"""
scene_detect.py — Stage 2: Scene change detection.

Uses PySceneDetect's ContentDetector to find timestamps where the video
cuts to a new scene/shot. These boundaries are used by the scorer to
reward candidate clips that start and end at natural cut points.

Also provides a --scene-cut mode that detects ALL scene changes and
exports every scene as a separate mp4 file.

Public functions:
    detect_scenes(video_path, cache_key, cache_dir) -> list[float]
    detect_scenes_full(video_path, cache_key, cache_dir) -> list[dict]
    export_all_scenes(video_path, scenes, output_dir) -> None
"""

import json
import subprocess
import sys
from pathlib import Path

from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector

from . import config


def _run_detection(video_path: str | Path, threshold: float | None = None):
    """Run PySceneDetect on a video and return the raw scene list.

    Args:
        video_path: Path to the source video file.
        threshold: ContentDetector threshold. Lower = more sensitive to
                   scene changes / camera angle shifts. If None, uses
                   config.SCENE_THRESHOLD.

    Returns:
        List of (start_timecode, end_timecode) tuples from PySceneDetect.
    """
    if threshold is None:
        threshold = config.SCENE_THRESHOLD

    video = open_video(str(video_path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))

    # Detect scenes — this processes the entire video frame by frame
    scene_manager.detect_scenes(video, show_progress=True)
    return scene_manager.get_scene_list()


def detect_scenes(
    video_path: str | Path,
    cache_key: str,
    cache_dir: Path,
) -> list[float]:
    """Detect scene/shot boundaries in a video file.

    Uses PySceneDetect's ContentDetector with a configurable threshold.
    Results are cached to disk keyed by cache_key.

    Args:
        video_path: Path to the source video file.
        cache_key: Unique key for caching (derived from video file identity).
        cache_dir: Directory to store cached results.

    Returns:
        Sorted list of scene-boundary timestamps in seconds.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"scenes_{cache_key}.json"

    # Check cache
    if cache_file.exists():
        print("  ✓ Scene boundaries found in cache, loading...")
        with open(cache_file, "r") as f:
            cached = json.load(f)
        return cached["boundaries"]

    print("  ⏳ Running scene detection (ContentDetector)...")

    scene_list = _run_detection(video_path)

    # Extract boundary timestamps
    boundaries = []
    for scene in scene_list:
        start_sec = scene[0].get_seconds()
        end_sec = scene[1].get_seconds()
        if start_sec > 0:
            boundaries.append(float(start_sec))
        if scene == scene_list[-1]:
            boundaries.append(float(end_sec))

    boundaries = sorted(set(boundaries))

    print(f"  ✓ Found {len(boundaries)} scene boundaries across {len(scene_list)} scenes.")

    # Cache
    cache_data = {
        "num_scenes": len(scene_list),
        "boundaries": boundaries,
        "scenes": [
            {
                "start": scene[0].get_seconds(),
                "end": scene[1].get_seconds(),
            }
            for scene in scene_list
        ],
    }
    with open(cache_file, "w") as f:
        json.dump(cache_data, f, indent=2)

    return boundaries


def detect_scenes_full(
    video_path: str | Path,
    cache_key: str,
    cache_dir: Path,
    threshold: float | None = None,
) -> list[dict]:
    """Detect all scenes and return full scene ranges (start + end).

    Like detect_scenes() but returns complete scene info for cutting.
    Uses a separate cache entry since the threshold may differ.

    Args:
        video_path: Path to the source video file.
        cache_key: Unique key for caching.
        cache_dir: Directory to store cached results.
        threshold: ContentDetector threshold override. Lower = more sensitive
                   (catches more camera angle / movement changes).

    Returns:
        List of dicts with keys: scene_num (int), start (float), end (float),
        duration (float).
    """
    effective_threshold = threshold if threshold is not None else config.SCENE_THRESHOLD
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"scenes_full_{cache_key}_t{effective_threshold}.json"

    # Check cache
    if cache_file.exists():
        print("  ✓ Full scene list found in cache, loading...")
        with open(cache_file, "r") as f:
            cached = json.load(f)
        print(f"  ✓ {len(cached['scenes'])} scenes loaded from cache.")
        return cached["scenes"]

    print(f"  ⏳ Running scene detection (threshold={effective_threshold})...")
    print("    Lower threshold = more sensitive to camera changes.")

    scene_list = _run_detection(video_path, threshold=effective_threshold)

    scenes = []
    for i, scene in enumerate(scene_list, 1):
        start = scene[0].get_seconds()
        end = scene[1].get_seconds()
        scenes.append({
            "scene_num": i,
            "start": round(float(start), 3),
            "end": round(float(end), 3),
            "duration": round(float(end - start), 3),
        })

    print(f"  ✓ Detected {len(scenes)} scenes.")

    # Cache
    with open(cache_file, "w") as f:
        json.dump({"threshold": effective_threshold, "scenes": scenes}, f, indent=2)

    return scenes


def _format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def export_all_scenes(
    video_path: str | Path,
    scenes: list[dict],
    output_dir: Path,
) -> None:
    """Export every detected scene as a separate mp4 file using ffmpeg.

    Each scene is cut precisely at its detected boundaries (frame-accurate
    with re-encoding) and saved as scene_001.mp4, scene_002.mp4, etc.

    Args:
        video_path: Path to the source video file.
        scenes: List of scene dicts from detect_scenes_full().
        output_dir: Directory to write the mp4 files into.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    video_path = Path(video_path)
    total = len(scenes)

    print(f"\n📦 Exporting {total} scenes to {output_dir}/")
    print()

    for scene in scenes:
        num = scene["scene_num"]
        start = scene["start"]
        end = scene["end"]
        duration = scene["duration"]

        output_file = output_dir / f"scene_{num:03d}_{_format_time(start).replace(':', '')}-{_format_time(end).replace(':', '')}.mp4"

        cmd = [
            "ffmpeg",
            "-ss", str(start),
            "-i", str(video_path),
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "aac",
            "-avoid_negative_ts", "make_zero",
            "-y",
            str(output_file),
        ]

        print(f"  ✂  Scene {num:3d}/{total}:  "
              f"{_format_time(start)} → {_format_time(end)}  "
              f"({duration:.1f}s) ", end="", flush=True)

        try:
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            print(f"✓ {output_file.name}")
        except FileNotFoundError:
            print("\n  ✗ ffmpeg not found. Please install ffmpeg.")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"✗ FAILED")
            print(f"    Error: {e.stderr.decode()[:200]}")

    print(f"\n✅ All {total} scenes exported to {output_dir}/")

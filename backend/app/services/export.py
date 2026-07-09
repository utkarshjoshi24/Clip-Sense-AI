"""
backend/app/services/export.py — EDL/FCPXML generation and ffmpeg clip cutting.

Supports:
  - CMX 3600 EDL format (DaVinci Resolve, Premiere Pro)
  - FCPXML format (Final Cut Pro, Premiere via XML import)
  - Server-side ffmpeg clip cutting → uploaded to S3
"""

import io
import logging
import subprocess
import tempfile
import uuid
from pathlib import Path

from ..config import get_settings
from ..models.clip import Clip
from ..services.storage import download_to_temp, generate_presigned_url, upload_fileobj

settings = get_settings()
logger = logging.getLogger(__name__)


def _format_edl_timecode(seconds: float, fps: float = 25.0) -> str:
    """Convert seconds to EDL timecode format HH:MM:SS:FF."""
    total_frames = int(seconds * fps)
    ff = total_frames % int(fps)
    ss = (total_frames // int(fps)) % 60
    mm = (total_frames // (int(fps) * 60)) % 60
    hh = total_frames // (int(fps) * 3600)
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def generate_edl(clips: list[Clip], video_name: str, fps: float = 25.0) -> str:
    """Generate a CMX 3600 EDL string for the selected clips.

    Compatible with DaVinci Resolve and Adobe Premiere Pro.

    Args:
        clips: List of Clip objects to include.
        video_name: Source video name (used as the reel name).
        fps: Frame rate for timecode conversion.

    Returns:
        EDL content as a string.
    """
    reel = Path(video_name).stem[:8].upper().replace(" ", "_")
    lines = [f"TITLE: {Path(video_name).stem} Highlights", "FCM: NON-DROP FRAME", ""]

    for i, clip in enumerate(clips, 1):
        tc_in = _format_edl_timecode(clip.start_time, fps)
        tc_out = _format_edl_timecode(clip.end_time, fps)
        rec_in = _format_edl_timecode((i - 1) * (clip.end_time - clip.start_time), fps)
        rec_out = _format_edl_timecode(i * (clip.end_time - clip.start_time), fps)

        lines.append(f"{i:03d}  {reel:<8}  AA/V  C  {tc_in} {tc_out} {rec_in} {rec_out}")
        if clip.title_suggestion:
            lines.append(f"* CLIP NAME: {clip.title_suggestion}")
        if clip.transcript_snippet:
            # EDL comments are prefixed with * and truncated
            snippet = clip.transcript_snippet[:80].replace("\n", " ")
            lines.append(f"* COMMENT: {snippet}")
        lines.append("")

    return "\n".join(lines)


def generate_fcpxml(clips: list[Clip], video_name: str, fps: float = 25.0) -> str:
    """Generate an FCPXML string for the selected clips.

    Compatible with Final Cut Pro and Adobe Premiere Pro.

    Args:
        clips: List of Clip objects to include.
        video_name: Source video name.
        fps: Frame rate for timecode conversion.

    Returns:
        FCPXML content as a string.
    """
    def _secs_to_rational(s: float, fps: float) -> str:
        """Convert seconds to FCP rational time (e.g. '100/25s')."""
        frames = round(s * fps)
        return f"{frames}/{int(fps)}s"

    asset_id = f"asset-{uuid.uuid4().hex[:8]}"
    format_id = f"format-{uuid.uuid4().hex[:8]}"
    stem = Path(video_name).stem

    clip_elements = []
    for i, clip in enumerate(clips):
        duration = clip.end_time - clip.start_time
        clip_elements.append(f"""
        <clip name="{clip.title_suggestion or f'Highlight {i+1}'}"
              offset="{_secs_to_rational(i * duration, fps)}"
              duration="{_secs_to_rational(duration, fps)}"
              start="{_secs_to_rational(clip.start_time, fps)}">
            <asset-clip ref="{asset_id}"
                        offset="{_secs_to_rational(clip.start_time, fps)}"
                        duration="{_secs_to_rational(duration, fps)}"
                        name="{clip.title_suggestion or f'Highlight {i+1}'}" />
        </clip>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.10">
    <resources>
        <format id="{format_id}" name="FFVideoFormat1080p{int(fps)}"
                frameDuration="1/{int(fps)}s" width="1920" height="1080" />
        <asset id="{asset_id}" name="{stem}"
               format="{format_id}" hasVideo="1" hasAudio="1">
            <media-rep kind="original-media" />
        </asset>
    </resources>
    <library>
        <event name="{stem} Highlights">
            <project name="{stem} Highlights">
                <sequence format="{format_id}"
                          tcStart="0/1s"
                          tcFormat="NDF">
                    <spine>
                        {''.join(clip_elements)}
                    </spine>
                </sequence>
            </project>
        </event>
    </library>
</fcpxml>"""
    return xml


def cut_clip_ffmpeg(
    video_storage_key: str,
    clip: Clip,
) -> str:
    """Download video from storage, cut the clip with ffmpeg, upload result.

    Returns the presigned URL for the exported clip.
    """
    output_key = f"exports/{clip.video_id}/{clip.id}.mp4"

    with download_to_temp(video_storage_key, suffix=".mp4") as video_path:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_out:
            out_path = Path(tmp_out.name)

        try:
            duration = clip.end_time - clip.start_time
            cmd = [
                "ffmpeg",
                "-ss", str(clip.start_time),
                "-i", str(video_path),
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",
                "-c:a", "aac",
                "-avoid_negative_ts", "make_zero",
                "-y",
                str(out_path),
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[:500]}")

            with open(out_path, "rb") as f:
                upload_fileobj(f, output_key, content_type="video/mp4")

            logger.info("Exported clip %s → %s", clip.id, output_key)
        finally:
            if out_path.exists():
                out_path.unlink()

    return generate_presigned_url(output_key, expiry_seconds=3600)

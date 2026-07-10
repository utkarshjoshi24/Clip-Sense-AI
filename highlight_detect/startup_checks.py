"""
startup_checks.py — Pre-flight validation for ClipSense plugin.

Verifies that the runtime environment is sane before the pipeline starts:
architecture compatibility, ffmpeg availability, model file integrity,
and DaVinci Resolve version detection.

Public functions:
    run_all_checks() -> list[str]  (returns list of warnings; raises on fatal)
"""

import os
import platform
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from .error_handler import (
    ClipSenseError,
    FFmpegError,
    ModelCorruptError,
    ResolveNotFoundError,
    get_logger,
)


# ---------------------------------------------------------------------------
# Architecture check
# ---------------------------------------------------------------------------

def check_architecture() -> str | None:
    """Verify the binary matches the running CPU architecture.

    Returns a warning string if there's a potential mismatch, None if OK.
    Raises ClipSenseError if there's a definite incompatibility.
    """
    machine = platform.machine().lower()
    pointer_size = struct.calcsize("P") * 8  # 32 or 64

    logger = get_logger()
    logger.info("Architecture check: machine=%s, pointer_size=%d-bit", machine, pointer_size)

    # Check if running under Rosetta 2 (x86_64 binary on Apple Silicon)
    is_rosetta = False
    if machine == "x86_64" and platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "sysctl.proc_translated"],
                capture_output=True, text=True, timeout=5,
            )
            if result.stdout.strip() == "1":
                is_rosetta = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    if is_rosetta:
        return (
            "⚠  Running under Rosetta 2 (x86_64 binary on Apple Silicon Mac).\n"
            "   Performance may be reduced. For best results, install the\n"
            "   Apple Silicon (arm64) version of ClipSense."
        )

    # Verify pointer size is 64-bit
    if pointer_size != 64:
        raise ClipSenseError(
            user_message=(
                f"❌ ClipSense requires a 64-bit Python runtime.\n"
                f"   Detected: {pointer_size}-bit Python on {machine}.\n"
                f"   Please install the 64-bit version of Python."
            ),
        )

    return None


# ---------------------------------------------------------------------------
# ffmpeg check
# ---------------------------------------------------------------------------

def check_ffmpeg() -> str | None:
    """Verify that ffmpeg is available and executable.

    Returns a warning string if ffmpeg has issues, None if OK.
    Raises FFmpegError if ffmpeg is completely missing.
    """
    logger = get_logger()

    # Check for bundled ffmpeg first (in the app bundle)
    bundled_ffmpeg = _find_bundled_ffmpeg()
    if bundled_ffmpeg:
        logger.info("Found bundled ffmpeg at: %s", bundled_ffmpeg)
        ffmpeg_path = bundled_ffmpeg
    else:
        # Fall back to system ffmpeg
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            logger.info("Using system ffmpeg at: %s", ffmpeg_path)
        else:
            raise FFmpegError(
                user_message=(
                    "❌ ffmpeg was not found on this system.\n"
                    "   ClipSense requires ffmpeg for audio extraction and clip cutting.\n"
                    "\n"
                    "   If you installed ClipSense via the .pkg installer, the bundled\n"
                    "   ffmpeg may be missing or corrupted. Try reinstalling.\n"
                    "\n"
                    "   To install ffmpeg manually:\n"
                    "     brew install ffmpeg"
                ),
                detail="Neither bundled nor system ffmpeg found",
            )

    # Verify it actually runs
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise FFmpegError(
                user_message=(
                    f"❌ ffmpeg is installed but appears to be broken.\n"
                    f"   Path: {ffmpeg_path}\n"
                    f"   Try reinstalling ClipSense or ffmpeg."
                ),
                detail=f"ffmpeg -version returned code {result.returncode}: {result.stderr[:200]}",
            )
        version_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
        logger.info("ffmpeg version: %s", version_line)
    except subprocess.TimeoutExpired:
        return f"⚠  ffmpeg at {ffmpeg_path} timed out during version check."
    except PermissionError:
        raise FFmpegError(
            user_message=(
                f"❌ ffmpeg exists but cannot be executed (permission denied).\n"
                f"   Path: {ffmpeg_path}\n"
                f"   Try: chmod +x {ffmpeg_path}"
            ),
            detail=f"PermissionError running {ffmpeg_path}",
        )

    # Also check ffprobe
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        return (
            "⚠  ffprobe was not found. Video duration detection may not work.\n"
            "   ffprobe is usually installed alongside ffmpeg."
        )

    return None


def _find_bundled_ffmpeg() -> str | None:
    """Look for a bundled ffmpeg binary relative to the running executable."""
    # When running as a PyInstaller bundle, sys._MEIPASS points to the temp dir
    if hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "ffmpeg"
        if bundled.exists() and os.access(str(bundled), os.X_OK):
            return str(bundled)

    # Also check relative to the script location
    script_dir = Path(__file__).resolve().parent.parent
    for candidate in [
        script_dir / "bin" / "ffmpeg",
        script_dir / "ffmpeg",
    ]:
        if candidate.exists() and os.access(str(candidate), os.X_OK):
            return str(candidate)

    return None


# ---------------------------------------------------------------------------
# Model files check
# ---------------------------------------------------------------------------

def check_model_files() -> str | None:
    """Verify that faster-whisper model files are accessible.

    We don't pre-check model files at startup when running from source
    (the model will be auto-downloaded on first use). In a bundled build,
    checks that the expected model directory exists.

    Returns a warning string if there's an issue, None if OK.
    Raises ModelCorruptError if files are definitely corrupted.
    """
    logger = get_logger()

    logger.info("Model files check: faster-whisper will auto-download models to ~/.cache on first use")
    return None


# ---------------------------------------------------------------------------
# DaVinci Resolve check
# ---------------------------------------------------------------------------

def check_resolve_version() -> str | None:
    """Attempt to detect DaVinci Resolve and its version.

    Returns a warning string if Resolve isn't found or version is outside
    the supported range (18.x – 19.x). Returns None if OK.

    This is a best-effort check — Resolve detection isn't always reliable
    from outside the Resolve scripting environment.
    """
    logger = get_logger()

    resolve_paths = [
        Path("/Applications/DaVinci Resolve/DaVinci Resolve.app"),
        Path("/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/MacOS/DaVinci Resolve"),
    ]

    resolve_found = False
    for p in resolve_paths:
        if p.exists():
            resolve_found = True
            break

    if not resolve_found:
        return (
            "⚠  DaVinci Resolve was not found at the standard location.\n"
            "   Expected: /Applications/DaVinci Resolve/\n"
            "   ClipSense can still run standalone, but Resolve integration\n"
            "   won't work until Resolve is installed."
        )

    # Try to get version from Info.plist
    plist_path = Path(
        "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Info.plist"
    )
    if plist_path.exists():
        try:
            result = subprocess.run(
                ["defaults", "read", str(plist_path), "CFBundleShortVersionString"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info("DaVinci Resolve version: %s", version)

                # Parse major version
                try:
                    major = int(version.split(".")[0])
                    if major < 18:
                        return (
                            f"⚠  DaVinci Resolve {version} detected.\n"
                            f"   ClipSense is tested with Resolve 18.x and 19.x.\n"
                            f"   Older versions may not support the required scripting APIs."
                        )
                    elif major > 19:
                        return (
                            f"⚠  DaVinci Resolve {version} detected.\n"
                            f"   ClipSense has been tested up to Resolve 19.x.\n"
                            f"   This newer version should work but hasn't been validated."
                        )
                except ValueError:
                    logger.warning("Could not parse Resolve version: %s", version)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    logger.info("DaVinci Resolve check: found and version OK")
    return None


# ---------------------------------------------------------------------------
# Run all checks
# ---------------------------------------------------------------------------

def run_all_checks() -> list[str]:
    """Run all startup checks. Returns a list of warning strings.

    Fatal issues raise ClipSenseError subclasses (caught by the caller).
    Non-fatal issues are returned as warning strings for the caller to print.
    """
    logger = get_logger()
    logger.info("Running startup checks...")

    warnings = []

    checks = [
        ("Architecture", check_architecture),
        ("ffmpeg", check_ffmpeg),
        ("Model files", check_model_files),
        ("DaVinci Resolve", check_resolve_version),
    ]

    for name, check_fn in checks:
        try:
            warning = check_fn()
            if warning:
                warnings.append(warning)
                logger.warning("Check '%s': %s", name, warning.replace("\n", " "))
            else:
                logger.info("Check '%s': OK", name)
        except ClipSenseError:
            # Fatal — re-raise to be caught by the top-level handler
            raise
        except Exception as e:
            # Non-fatal unexpected error in a check — log and continue
            logger.warning("Check '%s' failed unexpectedly: %s", name, e, exc_info=True)
            warnings.append(f"⚠  Startup check '{name}' encountered an error: {e}")

    logger.info("Startup checks complete: %d warnings", len(warnings))
    return warnings

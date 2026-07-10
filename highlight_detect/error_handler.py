"""
error_handler.py — Centralized error handling and logging for ClipSense.

Provides structured exception types with user-facing messages, file-based
logging to ~/Library/Logs/ClipSense/, and utilities for common failure
detection (disk space, permissions, etc.).

Public functions:
    setup_logging() -> logging.Logger
    handle_exception(exc) -> None
    check_disk_space(path, required_mb) -> None
    check_permissions(path, need_write) -> None

Exception classes:
    ClipSenseError (base)
    ResolveNotFoundError
    FFmpegError
    ModelCorruptError
    DiskSpaceError
    PermissionDeniedError
    VideoFormatError
"""

import logging
import os
import platform
import shutil
import stat
import sys
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


# ---------------------------------------------------------------------------
# Log directory — predictable location for bug reports
# ---------------------------------------------------------------------------
LOG_DIR = Path.home() / "Library" / "Logs" / "ClipSense"
LOG_FILE = LOG_DIR / "clipsense.log"
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 3


# ---------------------------------------------------------------------------
# Custom exception hierarchy
# ---------------------------------------------------------------------------

class ClipSenseError(Exception):
    """Base exception for all ClipSense errors.

    Every subclass carries a `user_message` that is safe to display
    directly to the end user (no stack traces, no internal paths).
    """

    def __init__(self, user_message: str, technical_detail: str = ""):
        self.user_message = user_message
        self.technical_detail = technical_detail
        super().__init__(user_message)


class ResolveNotFoundError(ClipSenseError):
    """DaVinci Resolve is missing, corrupted, or an unsupported version."""

    def __init__(self, detail: str = ""):
        super().__init__(
            user_message=(
                "❌ DaVinci Resolve was not found or is an unsupported version.\n"
                "   ClipSense requires DaVinci Resolve 18.x or 19.x.\n"
                "   Please install or update Resolve from:\n"
                "   https://www.blackmagicdesign.com/products/davinciresolve"
            ),
            technical_detail=detail,
        )


class FFmpegError(ClipSenseError):
    """ffmpeg binary is missing, corrupted, or failed to process a file."""

    def __init__(self, user_message: str = "", detail: str = ""):
        if not user_message:
            user_message = (
                "❌ ffmpeg encountered an error.\n"
                "   This may mean the bundled ffmpeg is missing or corrupted.\n"
                "   Try reinstalling ClipSense to fix this."
            )
        super().__init__(user_message=user_message, technical_detail=detail)


class ModelCorruptError(ClipSenseError):
    """Transcription model files are missing or corrupted."""

    def __init__(self, detail: str = ""):
        super().__init__(
            user_message=(
                "❌ Transcription model files are missing or corrupted.\n"
                "   This can happen if the installation was interrupted.\n"
                "   Please reinstall ClipSense to restore the model files."
            ),
            technical_detail=detail,
        )


class DiskSpaceError(ClipSenseError):
    """Insufficient disk space for processing."""

    def __init__(self, path: str, required_mb: float, available_mb: float):
        super().__init__(
            user_message=(
                f"❌ Not enough disk space to process this video.\n"
                f"   Location: {path}\n"
                f"   Required: ~{required_mb:.0f} MB\n"
                f"   Available: {available_mb:.0f} MB\n"
                f"   Free up some space and try again."
            ),
            technical_detail=f"path={path}, required={required_mb}MB, available={available_mb}MB",
        )


class PermissionDeniedError(ClipSenseError):
    """macOS permission issue — file access denied."""

    def __init__(self, path: str, operation: str = "access", detail: str = ""):
        super().__init__(
            user_message=(
                f"❌ Permission denied: cannot {operation} '{Path(path).name}'.\n"
                f"   Full path: {path}\n"
                f"\n"
                f"   On macOS, this is often caused by privacy restrictions.\n"
                f"   To fix this:\n"
                f"   1. Open System Settings → Privacy & Security → Files and Folders\n"
                f"   2. Find DaVinci Resolve (or Terminal) in the list\n"
                f"   3. Enable access to the folder containing your video files\n"
                f"\n"
                f"   Alternatively, try moving your video to ~/Movies or ~/Desktop."
            ),
            technical_detail=detail,
        )


class VideoFormatError(ClipSenseError):
    """Video file is corrupt or uses an unsupported codec."""

    def __init__(self, video_path: str, detail: str = ""):
        super().__init__(
            user_message=(
                f"❌ This video's format couldn't be read: {Path(video_path).name}\n"
                f"   The file may be corrupted, incomplete, or use a codec that\n"
                f"   ffmpeg doesn't support.\n"
                f"\n"
                f"   Try:\n"
                f"   • Re-exporting the video from your editing software\n"
                f"   • Converting it to H.264 MP4 with HandBrake or similar\n"
                f"   • Checking if the file plays correctly in VLC or QuickTime"
            ),
            technical_detail=detail,
        )


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

_logger = None


def setup_logging() -> logging.Logger:
    """Configure file + console logging for ClipSense.

    Creates ~/Library/Logs/ClipSense/ if it doesn't exist.
    Returns the configured root logger for the clipsense namespace.
    """
    global _logger
    if _logger is not None:
        return _logger

    # Create log directory
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        # If we can't create the log dir, fall back to stderr only
        print(f"⚠  Could not create log directory {LOG_DIR}: {e}", file=sys.stderr)
        _logger = logging.getLogger("clipsense")
        _logger.addHandler(logging.StreamHandler(sys.stderr))
        _logger.setLevel(logging.DEBUG)
        return _logger

    logger = logging.getLogger("clipsense")
    logger.setLevel(logging.DEBUG)

    # File handler — rotating, with timestamps
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_LOG_SIZE,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        print(f"⚠  Could not create log file {LOG_FILE}: {e}", file=sys.stderr)

    # Console handler — only warnings and above (to not clutter pipeline output)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    _logger = logger
    logger.info(
        "ClipSense logging initialized. Python %s, macOS %s, arch %s",
        platform.python_version(),
        platform.mac_ver()[0] or "unknown",
        platform.machine(),
    )
    return logger


def get_logger() -> logging.Logger:
    """Get the ClipSense logger, initializing if needed."""
    global _logger
    if _logger is None:
        return setup_logging()
    return _logger


# ---------------------------------------------------------------------------
# Top-level exception handler
# ---------------------------------------------------------------------------

def handle_exception(exc: Exception) -> None:
    """Handle an exception: log full traceback + print user-friendly message.

    For ClipSenseError subclasses, prints the user_message.
    For unexpected exceptions, prints a generic message with log file path.
    Always logs the full traceback to the log file.
    """
    logger = get_logger()

    if isinstance(exc, ClipSenseError):
        # Known error — log details, show user message
        logger.error(
            "%s: %s | technical: %s",
            type(exc).__name__,
            exc.user_message,
            exc.technical_detail,
        )
        logger.debug("Full traceback:", exc_info=True)
        print(f"\n{exc.user_message}", file=sys.stderr)
    else:
        # Unexpected error — log everything, show generic message
        logger.critical("Unhandled exception: %s", exc, exc_info=True)
        print(
            f"\n❌ ClipSense encountered an unexpected error.\n"
            f"   Error: {type(exc).__name__}: {exc}\n"
            f"\n"
            f"   A detailed log has been saved to:\n"
            f"   {LOG_FILE}\n"
            f"\n"
            f"   Please include this log file when reporting a bug.",
            file=sys.stderr,
        )

    # Always tell the user where the log file is
    if LOG_FILE.exists():
        print(f"\n📄 Log file: {LOG_FILE}", file=sys.stderr)


def install_excepthook():
    """Install a sys.excepthook that catches truly unhandled exceptions."""
    original_hook = sys.excepthook

    def clipsense_excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            # Don't catch Ctrl+C
            original_hook(exc_type, exc_value, exc_tb)
            return

        logger = get_logger()
        logger.critical(
            "Unhandled exception (excepthook): %s: %s",
            exc_type.__name__,
            exc_value,
            exc_info=(exc_type, exc_value, exc_tb),
        )
        print(
            f"\n❌ ClipSense crashed unexpectedly.\n"
            f"   Error: {exc_type.__name__}: {exc_value}\n"
            f"\n"
            f"   A detailed log has been saved to:\n"
            f"   {LOG_FILE}\n"
            f"\n"
            f"   Please include this log file when reporting a bug.",
            file=sys.stderr,
        )

    sys.excepthook = clipsense_excepthook


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

def check_disk_space(path: str | Path, required_mb: float = 500) -> None:
    """Check if there's enough disk space at the given path.

    Args:
        path: Path to check (uses the volume containing this path).
        required_mb: Minimum required space in megabytes.

    Raises:
        DiskSpaceError: If available space is less than required.
    """
    path = Path(path)

    # Find the actual mount point
    check_path = path if path.exists() else path.parent
    while not check_path.exists() and check_path.parent != check_path:
        check_path = check_path.parent

    try:
        usage = shutil.disk_usage(str(check_path))
        available_mb = usage.free / (1024 * 1024)

        if available_mb < required_mb:
            raise DiskSpaceError(
                path=str(path),
                required_mb=required_mb,
                available_mb=available_mb,
            )
    except OSError as e:
        get_logger().warning("Could not check disk space at %s: %s", path, e)


def check_permissions(path: str | Path, need_write: bool = False) -> None:
    """Check if the current process can access the given path.

    Args:
        path: Path to check.
        need_write: If True, also checks write permission.

    Raises:
        PermissionDeniedError: If access is denied.
    """
    path = Path(path)

    if not path.exists():
        return  # Can't check permissions on non-existent paths

    # Check read access
    if not os.access(str(path), os.R_OK):
        raise PermissionDeniedError(
            path=str(path),
            operation="read",
            detail=f"os.access(R_OK) returned False for {path}",
        )

    # Check write access if needed
    if need_write and not os.access(str(path), os.W_OK):
        raise PermissionDeniedError(
            path=str(path),
            operation="write to",
            detail=f"os.access(W_OK) returned False for {path}",
        )

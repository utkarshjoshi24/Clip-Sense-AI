#!/usr/bin/env bash
# build_macos.sh — Build ClipSense standalone macOS binary via PyInstaller.
#
# Usage:
#   bash scripts/build_macos.sh                    # auto-detect architecture
#   bash scripts/build_macos.sh --arch arm64       # Apple Silicon
#   bash scripts/build_macos.sh --arch x86_64      # Intel
#
# Output: dist/ClipSense-{arch}/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
ARCH=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --arch)
            ARCH="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: bash scripts/build_macos.sh [--arch arm64|x86_64]"
            exit 1
            ;;
    esac
done

# Auto-detect architecture if not specified
if [[ -z "$ARCH" ]]; then
    ARCH="$(uname -m)"
    echo "ℹ  Auto-detected architecture: $ARCH"
fi

# Validate
if [[ "$ARCH" != "arm64" && "$ARCH" != "x86_64" ]]; then
    echo "✗ Unsupported architecture: $ARCH (expected arm64 or x86_64)"
    exit 1
fi

echo "============================================================"
echo "  🔨  ClipSense macOS Build"
echo "============================================================"
echo "  Architecture:  $ARCH"
echo "  Project root:  $PROJECT_ROOT"
echo "  Python:        $(python3 --version 2>&1)"
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Create/activate virtual environment
# ---------------------------------------------------------------------------
VENV_DIR="$PROJECT_ROOT/.build_venv_${ARCH}"

echo "📦 Setting up build virtual environment..."
if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "  ⏳ Installing dependencies..."
pip install --quiet --upgrade pip setuptools wheel
pip install --quiet -r "$PROJECT_ROOT/requirements.txt"
pip install --quiet pyinstaller

echo "  ✓ Dependencies installed."

# ---------------------------------------------------------------------------
# Step 2: Download architecture-specific ffmpeg if not present
# ---------------------------------------------------------------------------
FFMPEG_DIR="$PROJECT_ROOT/bin"
FFMPEG_BIN="$FFMPEG_DIR/ffmpeg"

if [[ ! -x "$FFMPEG_BIN" ]]; then
    echo ""
    echo "📦 Downloading static ffmpeg for $ARCH..."
    mkdir -p "$FFMPEG_DIR"

    if [[ "$ARCH" == "arm64" ]]; then
        FFMPEG_URL="https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip"
    else
        FFMPEG_URL="https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip"
    fi

    echo "  ⚠  ffmpeg must be manually placed at: $FFMPEG_BIN"
    echo "  Download from: https://evermeet.cx/ffmpeg/ (choose your arch)"
    echo "  Or install via: brew install ffmpeg"
    echo ""
    echo "  Falling back to system ffmpeg for this build."
    FFMPEG_BIN="$(which ffmpeg 2>/dev/null || echo "")"

    if [[ -z "$FFMPEG_BIN" ]]; then
        echo "  ✗ ffmpeg not found. Install it first: brew install ffmpeg"
        exit 1
    fi
    echo "  ✓ Using system ffmpeg: $FFMPEG_BIN"
else
    echo "  ✓ Using bundled ffmpeg: $FFMPEG_BIN"
fi

# ---------------------------------------------------------------------------
# Step 3: Run PyInstaller
# ---------------------------------------------------------------------------
echo ""
echo "🔨 Building standalone binary with PyInstaller..."

DIST_DIR="$PROJECT_ROOT/dist/ClipSense-${ARCH}"
BUILD_DIR="$PROJECT_ROOT/build/pyinstaller-${ARCH}"

# Clean previous build
rm -rf "$DIST_DIR" "$BUILD_DIR"

# Determine the ctranslate2 library location for bundling
CT2_SITE_PKG="$(python3 -c "import ctranslate2; print(ctranslate2.__path__[0])" 2>/dev/null || echo "")"

HIDDEN_IMPORTS=(
    "--hidden-import=faster_whisper"
    "--hidden-import=ctranslate2"
    "--hidden-import=huggingface_hub"
    "--hidden-import=tokenizers"
    "--hidden-import=librosa"
    "--hidden-import=scipy"
    "--hidden-import=scipy.signal"
    "--hidden-import=numpy"
    "--hidden-import=scenedetect"
)

COLLECT_DATA=(
    "--collect-data=faster_whisper"
)

# Add ctranslate2 shared libs if found
EXTRA_ARGS=()
if [[ -n "$CT2_SITE_PKG" ]]; then
    COLLECT_DATA+=("--collect-all=ctranslate2")
fi

pyinstaller \
    --name clipsense \
    --onedir \
    --noconfirm \
    --clean \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR" \
    --specpath "$BUILD_DIR" \
    "${HIDDEN_IMPORTS[@]}" \
    "${COLLECT_DATA[@]}" \
    --add-data "$PROJECT_ROOT/hook_words.txt:." \
    --target-arch "$ARCH" \
    --log-level WARN \
    "$PROJECT_ROOT/run.py"

echo "  ✓ PyInstaller build complete."

# ---------------------------------------------------------------------------
# Step 4: Copy ffmpeg into the bundle
# ---------------------------------------------------------------------------
if [[ -x "$FFMPEG_BIN" ]]; then
    echo "📦 Bundling ffmpeg..."
    cp "$FFMPEG_BIN" "$DIST_DIR/clipsense/"
    chmod +x "$DIST_DIR/clipsense/ffmpeg"
    echo "  ✓ ffmpeg bundled."
fi

# ---------------------------------------------------------------------------
# Step 5: Report
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  ✅  Build Complete"
echo "============================================================"
BUNDLE_SIZE="$(du -sh "$DIST_DIR/clipsense" | cut -f1)"
echo "  Output:  $DIST_DIR/clipsense/"
echo "  Size:    $BUNDLE_SIZE"
echo "  Arch:    $ARCH"
echo ""

# Size warning
SIZE_BYTES="$(du -s "$DIST_DIR/clipsense" | cut -f1)"
SIZE_MB=$((SIZE_BYTES / 1024))
if [[ $SIZE_MB -gt 500 ]]; then
    echo "  ⚠  WARNING: Bundle exceeds 500MB ($SIZE_MB MB)."
    echo "     Review dependencies — faster-whisper bundles should be <400MB."
fi

echo "  To test: $DIST_DIR/clipsense/clipsense --help"
echo "============================================================"

deactivate

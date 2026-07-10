#!/usr/bin/env bash
# package_installer.sh — Create a .pkg installer for ClipSense.
#
# Usage:
#   bash scripts/package_installer.sh                    # auto-detect arch
#   bash scripts/package_installer.sh --arch arm64       # Apple Silicon
#   bash scripts/package_installer.sh --arch x86_64      # Intel
#
# Prerequisites:
#   - Run scripts/build_macos.sh first to create the PyInstaller bundle.
#
# Output: dist/ClipSense-{arch}.pkg

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
            exit 1
            ;;
    esac
done

if [[ -z "$ARCH" ]]; then
    ARCH="$(uname -m)"
fi

echo "============================================================"
echo "  📦  ClipSense Installer Packaging"
echo "============================================================"
echo "  Architecture:  $ARCH"
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# Validate PyInstaller output exists
# ---------------------------------------------------------------------------
BUNDLE_DIR="$PROJECT_ROOT/dist/ClipSense-${ARCH}/clipsense"

if [[ ! -d "$BUNDLE_DIR" ]]; then
    echo "✗ PyInstaller bundle not found at: $BUNDLE_DIR"
    echo "  Run scripts/build_macos.sh first."
    exit 1
fi

# ---------------------------------------------------------------------------
# Prepare installation layout
# ---------------------------------------------------------------------------
PKG_ROOT="$PROJECT_ROOT/build/pkg-root-${ARCH}"
INSTALL_DIR="$PKG_ROOT/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/ClipSense"
SCRIPTS_DIR="$PROJECT_ROOT/build/pkg-scripts-${ARCH}"

rm -rf "$PKG_ROOT" "$SCRIPTS_DIR"
mkdir -p "$INSTALL_DIR"
mkdir -p "$SCRIPTS_DIR"

echo "📋 Preparing installation layout..."

# Copy the PyInstaller bundle
cp -R "$BUNDLE_DIR/"* "$INSTALL_DIR/"

# Copy uninstall script
if [[ -f "$SCRIPT_DIR/uninstall_clipsense.sh" ]]; then
    cp "$SCRIPT_DIR/uninstall_clipsense.sh" "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/uninstall_clipsense.sh"
fi

# Create version marker
cat > "$INSTALL_DIR/.clipsense_version" << EOF
version=1.0.0-phase2
arch=$ARCH
build_date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
engine=faster-whisper
EOF

echo "  ✓ Installation layout prepared."

# ---------------------------------------------------------------------------
# Create postinstall script
# ---------------------------------------------------------------------------
cat > "$SCRIPTS_DIR/postinstall" << 'POSTINSTALL'
#!/usr/bin/env bash
# ClipSense .pkg postinstall script

INSTALL_DIR="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/ClipSense"
LOG_DIR="$HOME/Library/Logs/ClipSense"

echo "ClipSense postinstall: setting up..."

# Create log directory
mkdir -p "$LOG_DIR" 2>/dev/null || true

# Set executable permissions
if [[ -f "$INSTALL_DIR/clipsense" ]]; then
    chmod +x "$INSTALL_DIR/clipsense"
fi
if [[ -f "$INSTALL_DIR/ffmpeg" ]]; then
    chmod +x "$INSTALL_DIR/ffmpeg"
fi

# Architecture compatibility check
EXPECTED_ARCH=""
if [[ -f "$INSTALL_DIR/.clipsense_version" ]]; then
    EXPECTED_ARCH=$(grep "^arch=" "$INSTALL_DIR/.clipsense_version" | cut -d= -f2)
fi

CURRENT_ARCH="$(uname -m)"
if [[ -n "$EXPECTED_ARCH" && "$EXPECTED_ARCH" != "$CURRENT_ARCH" ]]; then
    # Not a fatal error — Rosetta 2 may handle x86_64 on arm64
    if [[ "$CURRENT_ARCH" == "arm64" && "$EXPECTED_ARCH" == "x86_64" ]]; then
        echo "⚠  Note: You've installed the Intel (x86_64) version on Apple Silicon."
        echo "   It will work via Rosetta 2 but an arm64 build would be faster."
    elif [[ "$CURRENT_ARCH" == "x86_64" && "$EXPECTED_ARCH" == "arm64" ]]; then
        echo "✗ ERROR: You've installed the Apple Silicon (arm64) version on an Intel Mac."
        echo "  This will NOT work. Please download the Intel (x86_64) installer."
    fi
fi

echo "ClipSense postinstall: done."
echo "  Install location: $INSTALL_DIR"
echo "  Log directory:    $LOG_DIR"
exit 0
POSTINSTALL

chmod +x "$SCRIPTS_DIR/postinstall"

echo "  ✓ Postinstall script created."

# ---------------------------------------------------------------------------
# Build .pkg with pkgbuild
# ---------------------------------------------------------------------------
echo ""
echo "🔨 Building component package..."

COMPONENT_PKG="$PROJECT_ROOT/build/ClipSense-component-${ARCH}.pkg"
IDENTIFIER="com.clipsense.plugin"
VERSION="1.0.0"

pkgbuild \
    --root "$PKG_ROOT" \
    --identifier "$IDENTIFIER" \
    --version "$VERSION" \
    --scripts "$SCRIPTS_DIR" \
    --install-location "/" \
    "$COMPONENT_PKG"

echo "  ✓ Component package built."

# ---------------------------------------------------------------------------
# Build final .pkg with productbuild
# ---------------------------------------------------------------------------
echo ""
echo "📦 Building final installer package..."

FINAL_PKG="$PROJECT_ROOT/dist/ClipSense-${ARCH}.pkg"

# Create distribution XML
DIST_XML="$PROJECT_ROOT/build/distribution-${ARCH}.xml"
cat > "$DIST_XML" << EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>ClipSense — AI Highlight Detection for DaVinci Resolve</title>
    <welcome file="welcome.txt"/>
    <license file="license.txt"/>
    <options customize="never" require-scripts="false" hostArchitectures="$ARCH"/>
    <choices-outline>
        <line choice="default">
            <line choice="com.clipsense.plugin"/>
        </line>
    </choices-outline>
    <choice id="default"/>
    <choice id="com.clipsense.plugin" visible="false">
        <pkg-ref id="com.clipsense.plugin"/>
    </choice>
    <pkg-ref id="com.clipsense.plugin" version="$VERSION" onConclusion="none">ClipSense-component-${ARCH}.pkg</pkg-ref>
</installer-gui-script>
EOF

# Create welcome and license text
RESOURCES_DIR="$PROJECT_ROOT/build/pkg-resources-${ARCH}"
mkdir -p "$RESOURCES_DIR"

cat > "$RESOURCES_DIR/welcome.txt" << EOF
Welcome to ClipSense

ClipSense is an AI-powered highlight detection plugin for DaVinci Resolve.

This installer will place ClipSense in:
/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/ClipSense/

Architecture: $ARCH
Engine: faster-whisper (CTranslate2)

Requirements:
- macOS 12.0 or later
- DaVinci Resolve 18.x or 19.x
EOF

cat > "$RESOURCES_DIR/license.txt" << EOF
ClipSense — MIT License

Copyright (c) 2024-2026 Utkarsh Joshi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF

productbuild \
    --distribution "$DIST_XML" \
    --resources "$RESOURCES_DIR" \
    --package-path "$PROJECT_ROOT/build" \
    "$FINAL_PKG"

echo "  ✓ Final installer package built."

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  ✅  Installer Packaging Complete"
echo "============================================================"
PKG_SIZE_MB=$(du -m "$FINAL_PKG" | cut -f1)
echo "  Installer:  $FINAL_PKG"
echo "  Size:       ${PKG_SIZE_MB} MB"
echo "  Arch:       $ARCH"
echo ""

if [[ $PKG_SIZE_MB -gt 500 ]]; then
    echo "  ⚠  WARNING: Installer exceeds 500MB target (${PKG_SIZE_MB} MB)."
    echo "     The faster-whisper approach should produce <400MB installers."
    echo "     Review bundled dependencies for unnecessary bloat."
else
    echo "  ✓ Size is within the 500MB target."
fi

echo ""
echo "  To install: sudo installer -pkg $FINAL_PKG -target /"
echo "  To uninstall: bash scripts/uninstall_clipsense.sh"
echo "============================================================"

#!/usr/bin/env bash
# uninstall_clipsense.sh — Cleanly remove ClipSense from macOS.
#
# Usage:
#   bash uninstall_clipsense.sh              # perform uninstall
#   bash uninstall_clipsense.sh --dry-run    # show what would be removed
#
# This removes:
#   - Plugin files from DaVinci Resolve's scripts directory
#   - Log files from ~/Library/Logs/ClipSense/
#   - Cached model files from ~/.cache/huggingface/hub/models--*whisper*
#   - The pkg receipt (so macOS knows it's uninstalled)

set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "🔍 DRY RUN — showing what would be removed (no changes made)"
    echo ""
fi

INSTALL_DIR="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/ClipSense"
LOG_DIR="$HOME/Library/Logs/ClipSense"
MODEL_CACHE_DIR="$HOME/.cache/huggingface/hub"
PKG_ID="com.clipsense.plugin"

echo "============================================================"
echo "  🗑  ClipSense Uninstaller"
echo "============================================================"
echo ""

FOUND_ANYTHING=false

# --- Plugin files ---
if [[ -d "$INSTALL_DIR" ]]; then
    FOUND_ANYTHING=true
    SIZE=$(du -sh "$INSTALL_DIR" 2>/dev/null | cut -f1)
    echo "📁 Plugin directory: $INSTALL_DIR ($SIZE)"
    if [[ "$DRY_RUN" == false ]]; then
        sudo rm -rf "$INSTALL_DIR"
        echo "   ✓ Removed."
    else
        echo "   → Would remove."
    fi
else
    echo "📁 Plugin directory: not found (already removed or not installed)"
fi
echo ""

# --- Log files ---
if [[ -d "$LOG_DIR" ]]; then
    FOUND_ANYTHING=true
    SIZE=$(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)
    echo "📄 Log directory: $LOG_DIR ($SIZE)"
    if [[ "$DRY_RUN" == false ]]; then
        rm -rf "$LOG_DIR"
        echo "   ✓ Removed."
    else
        echo "   → Would remove."
    fi
else
    echo "📄 Log directory: not found"
fi
echo ""

# --- Cached model files ---
if [[ -d "$MODEL_CACHE_DIR" ]]; then
    WHISPER_MODELS=$(find "$MODEL_CACHE_DIR" -maxdepth 1 -name "models--*whisper*" -type d 2>/dev/null || true)
    if [[ -n "$WHISPER_MODELS" ]]; then
        FOUND_ANYTHING=true
        echo "🧠 Cached Whisper model files:"
        while IFS= read -r model_dir; do
            SIZE=$(du -sh "$model_dir" 2>/dev/null | cut -f1)
            echo "   $model_dir ($SIZE)"
            if [[ "$DRY_RUN" == false ]]; then
                rm -rf "$model_dir"
                echo "   ✓ Removed."
            else
                echo "   → Would remove."
            fi
        done <<< "$WHISPER_MODELS"
    else
        echo "🧠 Cached model files: none found"
    fi
else
    echo "🧠 Model cache directory: not found"
fi
echo ""

# --- Cached processing files ---
CACHE_DIR="$HOME/.highlight_cache"
if [[ -d "$CACHE_DIR" ]]; then
    FOUND_ANYTHING=true
    SIZE=$(du -sh "$CACHE_DIR" 2>/dev/null | cut -f1)
    echo "💾 Processing cache: $CACHE_DIR ($SIZE)"
    if [[ "$DRY_RUN" == false ]]; then
        rm -rf "$CACHE_DIR"
        echo "   ✓ Removed."
    else
        echo "   → Would remove."
    fi
fi

# --- Forget pkg receipt ---
RECEIPT_EXISTS=$(pkgutil --pkgs 2>/dev/null | grep -c "$PKG_ID" || true)
if [[ "$RECEIPT_EXISTS" -gt 0 ]]; then
    FOUND_ANYTHING=true
    echo "📋 Package receipt: $PKG_ID"
    if [[ "$DRY_RUN" == false ]]; then
        sudo pkgutil --forget "$PKG_ID" 2>/dev/null || true
        echo "   ✓ Forgotten."
    else
        echo "   → Would forget."
    fi
else
    echo "📋 Package receipt: not found"
fi
echo ""

# --- Summary ---
echo "============================================================"
if [[ "$DRY_RUN" == true ]]; then
    echo "  🔍 Dry run complete — no changes were made."
    echo "  Run without --dry-run to perform the uninstall."
elif [[ "$FOUND_ANYTHING" == true ]]; then
    echo "  ✅ ClipSense has been uninstalled."
else
    echo "  ℹ  ClipSense was not found on this system."
fi
echo "============================================================"

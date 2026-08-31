#!/bin/bash
#
# force-icloud-upload.sh
#
# Nudges macOS's iCloud Drive daemon (bird) into re-checking and uploading
# files that appear "stuck" locally (spinning/pending iCloud icon in Finder).
#
# There is no public API to force-upload a specific file, so this script uses
# the standard workaround: touching each file's modification time flags it as
# changed, which makes bird re-evaluate and re-queue it for upload.
#
# Usage:
#   ./force-icloud-upload.sh [path] [-r] [-w] [-t seconds]
#
#   path         Directory to nudge (default: the Cegep Obsidian vault folder)
#   -r           Also restart the bird daemon (killall bird) for a harder
#                kick. This briefly pauses ALL iCloud Drive syncing on this
#                Mac while macOS relaunches it (a few seconds) — safe, but
#                system-wide, not scoped to this folder.
#   -w           Wait and show live upload progress after nudging.
#   -t seconds   Max time to wait with -w (default: 120).

set -euo pipefail

TARGET_DIR="/Users/etiennerivard/Library/Mobile Documents/iCloud~md~obsidian/Documents/Cegep"
CONTAINER="iCloud.md.obsidian"
RESTART_BIRD=0
WAIT_UPLOAD=0
WAIT_TIMEOUT=120

# First positional arg (if not an option) overrides the target directory
if [[ $# -gt 0 && "$1" != -* ]]; then
    TARGET_DIR="$1"
    shift
fi

while getopts "rwt:" opt; do
    case "$opt" in
        r) RESTART_BIRD=1 ;;
        w) WAIT_UPLOAD=1 ;;
        t) WAIT_TIMEOUT="$OPTARG" ;;
        *) echo "Usage: $0 [path] [-r] [-w] [-t seconds]" >&2; exit 1 ;;
    esac
done

if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: directory not found: $TARGET_DIR" >&2
    exit 1
fi

echo "Target: $TARGET_DIR"
echo

echo "== iCloud status before =="
brctl status "$CONTAINER" 2>&1 || true
echo

count=0
while IFS= read -r -d '' file; do
    touch "$file"
    ((count++))
done < <(find "$TARGET_DIR" -type f -not -name '.DS_Store' -print0)

echo "Nudged $count file(s) (updated modification time)."

if [ "$RESTART_BIRD" -eq 1 ]; then
    echo
    echo "Restarting bird daemon to force a full re-scan (system-wide, brief)..."
    killall bird 2>/dev/null || true
    sleep 2
fi

if [ "$WAIT_UPLOAD" -eq 1 ]; then
    echo
    echo "Waiting up to ${WAIT_TIMEOUT}s for uploads to complete..."
    brctl monitor -w -t "$WAIT_TIMEOUT" "$CONTAINER" || true
fi

echo
echo "== iCloud status after =="
brctl status "$CONTAINER" 2>&1 || true
echo
echo "Done. If files still show as pending, check Finder or run:"
echo "  brctl status $CONTAINER"

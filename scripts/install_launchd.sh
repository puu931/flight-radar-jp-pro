#!/bin/bash
# Install + load the Flight Radar launchd agent.
# Run once after deploying. Re-run to refresh the schedule.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_SRC="$REPO_DIR/scripts/com.puu931.flightradar.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.puu931.flightradar.plist"

if [ ! -f "$REPO_DIR/.venv/bin/python" ]; then
  echo "❌ .venv not found. Run from repo root:"
  echo "   python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt"
  exit 1
fi

mkdir -p "$REPO_DIR/logs"
mkdir -p "$HOME/Library/LaunchAgents"

# Unload any previous version cleanly (ignore errors on first install).
launchctl unload "$PLIST_DST" 2>/dev/null || true

cp "$PLIST_SRC" "$PLIST_DST"
launchctl load "$PLIST_DST"

echo "✅ Installed: $PLIST_DST"
echo "   Schedule: 09:00 / 15:00 / 23:00 local"
echo "   Logs:     $REPO_DIR/logs/scan.log"
echo ""
echo "Useful commands:"
echo "  launchctl list | grep flightradar    # confirm loaded"
echo "  launchctl start com.puu931.flightradar  # run now (manual test)"
echo "  tail -f $REPO_DIR/logs/scan.log"
echo "  launchctl unload $PLIST_DST          # disable"

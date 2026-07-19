#!/bin/bash
# SAST scanner: reads security.sast from stack.json and runs the configured command.
# Skips silently if security.sast is empty or not set.
#
# Usage: bash sast-scan.sh
# Or wire into CI / on-demand slash command.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAST_CMD=$(python3 "$SCRIPT_DIR/read-config.py" security.sast 2>/dev/null || true)

if [ -z "$SAST_CMD" ]; then
    echo "[sast-scan] security.sast not configured in stack.json — skipping."
    exit 0
fi

echo "[sast-scan] running: $SAST_CMD"
eval "$SAST_CMD"

#!/bin/bash

# OpenClaw Scheduler for Photo Automation
# Starts the photo culling workflow on an hourly schedule

set -e

PROJECT_ROOT="/Users/rmaski/Downloads/Photos-3-001/photo-automation"
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python" 

# Ensure virtual environment is active
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Python virtual environment not found at $VENV_PYTHON"
    exit 1
fi

cd "$PROJECT_ROOT"

echo "Starting OpenClaw Photo Culling Scheduler..."
echo "Configuration: .openclaw/config.yaml"
echo "Schedule: Every hour"
echo "Logs: ./openclaw_logs/"

# Run OpenClaw with the config
"$VENV_PYTHON" -m openclaw.daemon \
    --config .openclaw/config.yaml \
    --workflow photo-culling \
    --log-level info \
    --log-dir ./openclaw_logs

echo "OpenClaw scheduler stopped."

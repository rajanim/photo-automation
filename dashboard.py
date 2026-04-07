#!/usr/bin/env python3
"""
OpenClaw Photo Culling Dashboard

A web-based UI for monitoring the photo culling scheduler.
Shows job status, execution history, and detailed cull reports.
"""

from flask import Flask, render_template, jsonify, send_from_directory, abort
from pathlib import Path
import csv
import os
from datetime import datetime
import re

app = Flask(__name__)

# Project configuration
PROJECT_ROOT = Path(__file__).parent
LOG_DIR = PROJECT_ROOT / ".openclaw_logs"
CULLED_DIR = PROJECT_ROOT / "CULLED"
REJECTED_DIR = PROJECT_ROOT / "REJECTED"
RAW_DIR = PROJECT_ROOT / "RAW"
REPORT_FILE = PROJECT_ROOT / "cull_report.csv"

def get_scheduler_status():
    """Get current scheduler status from log file."""
    log_file = LOG_DIR / "scheduler.log"
    
    if not log_file.exists():
        return {
            "status": "unknown",
            "last_run": None,
            "next_run": None,
            "message": "Scheduler not started yet"
        }
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    if not lines:
        return {
            "status": "unknown",
            "last_run": None,
            "next_run": None,
            "message": "No log entries"
        }
    
    # Get last line for status
    last_line = lines[-1].strip()
    
    # Extract timestamps and status
    timestamps = [line[:19] for line in lines if line.strip() and len(line) > 19]
    last_run = timestamps[-1] if timestamps else None
    
    # Check if currently running (look for "Starting" in recent logs)
    is_running = any("Starting hourly" in line for line in lines[-10:])
    
    status = "running" if is_running else "idle"
    
    return {
        "status": status,
        "last_run": last_run,
        "started_at": timestamps[0] if timestamps else None,
        "message": last_line
    }

def get_image_counts():
    """Get counts of images in CULLED and REJECTED folders."""
    culled_count = len(list(CULLED_DIR.glob("*"))) if CULLED_DIR.exists() else 0
    rejected_count = len(list(REJECTED_DIR.glob("*"))) if REJECTED_DIR.exists() else 0
    
    return {
        "culled": culled_count,
        "rejected": rejected_count,
        "total": culled_count + rejected_count
    }

def get_cull_report():
    """Parse and return cull report data."""
    if not REPORT_FILE.exists():
        return {
            "rows": [],
            "summary": {}
        }
    
    rows = []
    decisions = {}
    reasons = {}
    
    with open(REPORT_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            file_name = row.get('file_name') or row.get('file') or ''
            decision = row.get('decision', '').strip().lower()

            image_dir = CULLED_DIR if decision == 'keep' else REJECTED_DIR
            image_path = image_dir / file_name if file_name else None

            if image_path and not image_path.exists() and file_name:
                raw_path = RAW_DIR / file_name
                image_path = raw_path if raw_path.exists() else None

            row['display_file'] = file_name
            row['image_url'] = f"/image/{decision}/{file_name}" if image_path else None

            rows.append(row)
            
            # Count decisions
            decision = row.get('decision', 'unknown')
            decisions[decision] = decisions.get(decision, 0) + 1
            
            # Count reasons
            reason = row.get('reason', 'unknown')
            if reason:
                reasons[reason] = reasons.get(reason, 0) + 1
    
    # Sort reasons by count
    top_reasons = sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "rows": rows[-50:],  # Last 50 entries
        "total_rows": len(rows),
        "summary": {
            "decisions": decisions,
            "top_reasons": [{"reason": r, "count": c} for r, c in top_reasons]
        }
    }

def get_execution_history():
    """Get execution history from log file."""
    log_file = LOG_DIR / "scheduler.log"
    
    if not log_file.exists():
        return []
    
    executions = []
    with open(log_file, 'r') as f:
        content = f.read()
    
    # Find all execution blocks
    execution_blocks = re.findall(
        r'========.*?(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?========',
        content,
        re.DOTALL
    )
    
    # Parse execution details from log
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if "Starting hourly photo culling task" in line:
            timestamp = line[:19]
            status = "completed"
            
            # Check if there's an error following
            for j in range(i, min(i+20, len(lines))):
                if "ERROR" in lines[j]:
                    status = "failed"
                    break
            
            executions.append({
                "timestamp": timestamp,
                "status": status
            })
    
    return executions[-10:]  # Last 10 executions

@app.route('/')
def index():
    """Render dashboard home page."""
    scheduler_status = get_scheduler_status()
    image_counts = get_image_counts()
    report = get_cull_report()
    execution_history = get_execution_history()
    
    return render_template('dashboard.html',
        status=scheduler_status,
        counts=image_counts,
        report=report,
        history=execution_history
    )

@app.route('/api/status')
def api_status():
    """API endpoint for scheduler status."""
    return jsonify(get_scheduler_status())

@app.route('/api/counts')
def api_counts():
    """API endpoint for image counts."""
    return jsonify(get_image_counts())

@app.route('/api/report')
def api_report():
    """API endpoint for cull report."""
    return jsonify(get_cull_report())

@app.route('/api/history')
def api_history():
    """API endpoint for execution history."""
    return jsonify(get_execution_history())

@app.route('/image/<decision>/<path:filename>')
def serve_report_image(decision, filename):
    """Serve images for report preview tiles."""
    decision = (decision or '').lower()

    if decision == 'keep':
        image_dir = CULLED_DIR
    elif decision == 'reject':
        image_dir = REJECTED_DIR
    else:
        image_dir = RAW_DIR

    if (image_dir / filename).exists():
        return send_from_directory(image_dir, filename)
    if (RAW_DIR / filename).exists():
        return send_from_directory(RAW_DIR, filename)

    abort(404)

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    template_dir = PROJECT_ROOT / "templates"
    template_dir.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("OpenClaw Photo Culling Dashboard")
    print("=" * 60)
    print(f"\n📊 Dashboard: http://localhost:5000")
    print(f"📁 Project: {PROJECT_ROOT}")
    print(f"📋 Logs: {LOG_DIR / 'scheduler.log'}")
    print(f"\nPress Ctrl+C to stop the dashboard\n")
    
    app.run(debug=False, host='localhost', port=5000)

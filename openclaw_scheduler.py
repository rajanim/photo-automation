#!/usr/bin/env python3
"""
OpenClaw Photo Culling Scheduler

Runs the photo culling automation every hour using OpenClaw's scheduling system.
"""

import sys
import os
from pathlib import Path
from openclaw import Workflow, Scheduler, Schedule

# Project configuration
PROJECT_ROOT = Path("/Users/rmaski/Downloads/Photos-3-001/photo-automation")
os.chdir(PROJECT_ROOT)

def create_cull_workflow():
    """Create the photo culling workflow task."""
    workflow = Workflow(
        name="photo-culling",
        description="Automated photo culling with quality filtering and deduplication"
    )
    
    # Add the main culling task
    workflow.add_task(
        name="cull_photos",
        command="python main.py",
        working_dir=str(PROJECT_ROOT),
        parameters={
            "source": "./RAW",
            "culled": "./CULLED",
            "rejected": "./REJECTED",
            "report": "./cull_report.csv",
            "duplicate_threshold": 7,
            "blur_threshold": 85,
            "min_pixels": 1000000,
            "underexposed": 30,
            "overexposed": 225,
            "top_per_day": 6,
        },
        timeout=300,
        on_failure="log_and_continue"
    )
    
    return workflow

def main():
    """Start the hourly scheduler."""
    print("Initializing OpenClaw Photo Culling Scheduler...")
    
    # Create workflow
    workflow = create_cull_workflow()
    
    # Create scheduler with hourly trigger
    scheduler = Scheduler(
        name="photo-scheduler",
        log_dir=".openclaw_logs",
        log_level="info"
    )
    
    # Add hourly schedule
    schedule = Schedule(
        workflow=workflow,
        trigger="hourly",
        description="Process photos every hour"
    )
    scheduler.add_schedule(schedule)
    
    print("✓ Workflow configured")
    print("✓ Schedule: Every hour")
    print("✓ Logs: .openclaw_logs/")
    print("\nStarting scheduler (runs in foreground)...")
    print("Press Ctrl+C to stop.\n")
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n\nScheduler stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

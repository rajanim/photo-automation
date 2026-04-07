#!/usr/bin/env python3
"""
OpenClaw Photo Culling Scheduler (Robust Implementation)

Runs the photo culling automation every hour with proper logging and error handling.
Uses the 'schedule' library for reliable hourly execution.
"""

import sys
import os
import time
import logging
import traceback
from pathlib import Path
from datetime import datetime
import subprocess

# Add current directory to path to import local modules
sys.path.insert(0, str(Path(__file__).parent))

try:
    import schedule
except ImportError:
    print("Installing required 'schedule' package...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "schedule"])
    import schedule

# Project configuration
PROJECT_ROOT = Path(__file__).parent
LOG_DIR = PROJECT_ROOT / ".openclaw_logs"
LOG_DIR.mkdir(exist_ok=True)

# Configure logging
def setup_logging():
    """Setup logging to both file and console."""
    log_file = LOG_DIR / "scheduler.log"
    
    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup logger
    logger = logging.getLogger("OpenClawScheduler")
    logger.setLevel(logging.INFO)
    
    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger

logger = setup_logging()

def run_culling_task():
    """Execute the photo culling pipeline."""
    logger.info("=" * 60)
    logger.info("Starting hourly photo culling task")
    logger.info("=" * 60)
    
    try:
        os.chdir(PROJECT_ROOT)
        
        # Run main.py with configured parameters
        cmd = [
            sys.executable, "main.py",
            "--source", "./RAW",
            "--culled", "./CULLED",
            "--rejected", "./REJECTED",
            "--report", "./cull_report.csv",
            "--duplicate-threshold", "7",
            "--blur-threshold", "85",
            "--min-pixels", "1000000",
            "--underexposed", "30",
            "--overexposed", "225",
            "--top-per-day", "6",
        ]
        
        logger.info(f"Executing: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.stdout:
            logger.info("Output:\n" + result.stdout)
        
        if result.returncode == 0:
            logger.info("✓ Photo culling completed successfully")
            logger.info(f"✓ Results in: CULLED/, REJECTED/, cull_report.csv")
            return True
        else:
            logger.error(f"✗ Process exited with code {result.returncode}")
            if result.stderr:
                logger.error(f"Error output:\n{result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("✗ Task timed out after 300 seconds")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        logger.error(traceback.format_exc())
        return False
    finally:
        logger.info("=" * 60)

def schedule_jobs():
    """Schedule the hourly culling job."""
    schedule.every().hour.at(":00").do(run_culling_task)
    logger.info("✓ Photo culling scheduled to run every hour at :00 seconds")

def main():
    """Main scheduler loop."""
    logger.info("OpenClaw Photo Culling Scheduler Started")
    logger.info(f"Project: {PROJECT_ROOT}")
    logger.info(f"Logs: {LOG_DIR}/")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")
    
    # Schedule the jobs
    schedule_jobs()
    
    # Run initial task immediately (optional, comment out to wait for next hour)
    logger.info("Running initial culling task...")
    run_culling_task()
    
    # Keep scheduler running
    logger.info("Entering scheduler loop. Press Ctrl+C to stop.\n")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute if a job needs to run
    except KeyboardInterrupt:
        logger.info("\n\n✓ Scheduler stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Scheduler error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()

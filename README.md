# Photo Automation Culling Workflow


## 1) Introduction

The initial request was to convert the photo selection process into an OpenClaw-style workflow that:

- Automatically flags bad images
- Automatically flags redundant (near-duplicate) images
- Leaves only the best candidate images for manual review

A follow-up request asked to add a second-stage ranking so only top images per day are kept.

## Demo
Watch the workflow in action: https://www.youtube.com/watch?v=zTYvNlcEjU0

## 2) What Is Implemented

The workflow now performs automated photo culling with the following stages:

1. Quality filtering
- Detects blurry images using Laplacian variance
- Detects low-resolution images via minimum pixel threshold
- Detects underexposed and overexposed images using grayscale brightness

2. Near-duplicate filtering
- Computes perceptual hash (pHash) per image
- Treats images as near-duplicates when hash distance <= threshold
- Keeps the higher quality image, rejects the weaker one

3. Daily top-N ranking (second-stage pruning)
- Groups remaining kept images by day (file modified date)
- Ranks each day by quality score
- Keeps only top N per day (configured as 6 in workflow)
- Moves excess images to REJECTED with explicit reason

4. Audit reporting
- Writes a CSV report with one row per processed file:
  - decision: keep/reject
  - reason
  - duplicate_of (when applicable)
  - blur_score, brightness, resolution, quality_score

## 3) Implementation Details

### Core Files

- `cull.py`
  - Main culling engine
  - Handles load, scoring, duplicate handling, daily ranking, and reporting

- `main.py`
  - Thin entrypoint that calls `cull.main()`

- `workflow.yaml`
  - Folder watch trigger on `./RAW`
  - Executes the culling command with configured thresholds and daily top-N

### Pipeline Logic (High Level)

1. Read all supported images from `RAW/`
2. Analyze each image:
   - blur score
   - brightness
   - resolution
   - pHash
   - weighted quality score
3. Immediately reject images failing quality gates
4. Deduplicate among remaining candidates using pHash distance
5. Keep only top N per day from deduplicated winners
6. Write final CSV report and output folders

### Quality Score Formula

Quality score is a weighted value in `compute_quality_score(...)`:

- Blur component: 55%
- Exposure component: 35%
- Resolution component: 10%

This score is used to decide winners among near-duplicates and for daily ranking.

### Current Workflow Command

Defined in `workflow.yaml`:

```bash
python main.py \
  --source ./RAW \
  --culled ./CULLED \
  --rejected ./REJECTED \
  --report ./cull_report.csv \
  --duplicate-threshold 7 \
  --blur-threshold 85 \
  --min-pixels 1000000 \
  --underexposed 30 \
  --overexposed 225 \
  --top-per-day 6
```

## 4) Input Data Summary

Run context used for current output:

- Input folder: `RAW/`
- Input files present: 44
- Supported mixed image formats (JPG/PNG/etc.)

## 5) Final Output Summary

After running the implemented pipeline:

- `RAW`: 44 files (source retained because run mode was copy)
- `CULLED`: 16 files (best candidates)
- `REJECTED`: 26 files (bad/redundant/excess)
- Report rows in `cull_report.csv`: 42

Decision totals from report:

- keep: 16
- reject: 26

Top reasons seen in report:

- `daily_ranking_excess:2026-04-04` -> 10
- `blurry` -> 8
- `low_resolution` -> 5
- plus smaller counts for overexposed and combined reasons

## 6) How To Run Manually

```bash
python main.py --source ./RAW --culled ./CULLED --rejected ./REJECTED --report ./cull_report.csv --duplicate-threshold 7 --blur-threshold 85 --min-pixels 1000000 --underexposed 30 --overexposed 225 --top-per-day 6
```

To move files instead of copy:

```bash
python main.py ... --move
```

To disable daily top-N pruning:

```bash
python main.py ... --top-per-day 0
```

## 7) Notes and Constraints

- Daily grouping currently uses file modified date (`mtime`) for robust cross-format support.
- If desired, this can be extended to prefer EXIF capture date with fallback to `mtime`.
- Existing helper files `blur.py` and previous partial logic are not required by the new pipeline path (`main.py` -> `cull.py`).

## 8) OpenClaw Integration and Hourly Scheduling

### Background: From Manual Workflow to OpenClaw Orchestration

**Original Implementation (Sections 1-7):**
- The photo culling pipeline was implemented as a standalone Python application
- Included a `workflow.yaml` file that used a folder-watch trigger
- Required manual execution or external orchestration tools
- Was designed following "OpenClaw-style" principles (deterministic, auditable, decision-based) but was **not** actually using the OpenClaw framework

**Why OpenClaw?**
To move from a conceptually-aligned workflow to actual OpenClaw integration, we introduced the official **OpenClaw** framework to:
- Provide robust scheduled execution (every hour)
- Enable proper logging and audit trails
- Handle failures with retry logic
- Centralize workflow orchestration
- Make the pipeline production-ready with daemon-style operation

### Installation

OpenClaw was installed via pip into the project's virtual environment:

```bash
pip install openclaw
```

Verify installation:
```bash
python -c "import openclaw; print('OpenClaw installed successfully')"
```

### Troubleshooting Installation

If you encounter errors during installation, follow these verified steps:

#### Step 1: Activate Virtual Environment

```bash
cd /Users/rmaski/Downloads/Photos-3-001
source .venv/bin/activate
```

**Expected output:** Your terminal prompt should show `(.venv)` prefix

#### Step 2: Install Required Python Dependencies

Install all image processing and scheduling libraries:

```bash
pip install opencv-python rawpy numpy pillow imagehash schedule
```

**What each package does:**
- `opencv-python` – Image analysis and blur detection
- `rawpy` – RAW image format support
- `numpy` – Numerical computations
- `pillow` – Image I/O and manipulation
- `imagehash` – Perceptual hashing for duplicate detection
- `schedule` – Reliable hourly job scheduling

**Expected output:** Should show successful installation of all 7 packages

#### Step 3: Verify Dependencies

Test that all imports work correctly:

```bash
python -c "import cv2, rawpy, numpy, PIL, imagehash, schedule; print('All dependencies installed successfully')"
```

**Expected output:** No errors, prints success message

#### Step 4: Run the Scheduler

From the photo-automation directory with venv activated:

```bash
cd /Users/rmaski/Downloads/Photos-3-001/photo-automation
python run_openclaw_scheduler.py
```

**Expected output:**
```
2026-04-05 05:52:25 - INFO - OpenClaw Photo Culling Scheduler Started
2026-04-05 05:52:25 - INFO - Project: /Users/rmaski/Downloads/Photos-3-001/photo-automation
2026-04-05 05:52:25 - INFO - ✓ Photo culling scheduled to run every hour at :00 seconds
2026-04-05 05:52:25 - INFO - Running initial culling task...
```

## Demo

Watch the workflow in action: [https://www.youtube.com/watch?v=zTYvNlcEjU0](https://www.youtube.com/watch?v=zTYvNlcEjU0)

#### Common Issues and Solutions

**Issue: `ModuleNotFoundError: No module named 'cv2'`**
- Cause: Dependencies not installed in active venv
- Solution: Ensure venv is activated (`source .venv/bin/activate`) and run step 2

**Issue: `error: externally-managed-environment`**
- Cause: System Python is protected; can't install packages directly
- Solution: Always use the virtual environment (Step 1)

**Issue: Python version too old (3.9 or earlier)**
- Cause: OpenClaw requires Python 3.10+
- Solution: Check Python version with `python --version` and upgrade if needed

**Issue: Port 8080 already in use**
- Cause: Another process using the same port
- Solution: Use different port or kill the existing process: `lsof -i :8080`

### OpenClaw Configuration Files

New files created in `.openclaw/` directory:

**1. `.openclaw/config.yaml` — Main Configuration**
- Defines the hourly schedule trigger
- Specifies task parameters (blur threshold, duplicate threshold, daily top-N, etc.)
- Configures error handling (retry logic, timeout)
- Sets output monitoring and logging

**2. `run_openclaw_scheduler.py` — Robust Python Scheduler (Recommended)**
- Runs the photo culling pipeline every hour at the top of the hour
- Uses Python's `schedule` library for reliable execution
- Provides detailed logging to `.openclaw_logs/scheduler.log`
- Handles process errors and captures output
- Can be run in foreground or background

**3. `openclaw_scheduler.py` — Alternative OpenClaw Integration**
- Direct Python integration with OpenClaw's Workflow and Scheduler classes
- Alternative implementation using OpenClaw's native API
- Useful for advanced customization

**4. `.openclaw/start-scheduler.sh` — Bash Startup Script**
- Shell script wrapper for daemon-style execution
- Ensures correct Python environment is used
- Provides simple start/stop interface

**5. `.openclaw/README.md` — Detailed OpenClaw Guide**
- Complete usage instructions
- Monitoring and troubleshooting tips
- Configuration adjustment guide
- macOS system integration (launchd)
- Background execution methods

### How OpenClaw Runs

#### Method 1: Python Scheduler (Recommended)

```bash
cd /Users/rmaski/Downloads/Photos-3-001/photo-automation
python run_openclaw_scheduler.py
```

**Execution flow:**
1. Scheduler starts and logs configuration
2. Runs photo culling task immediately (first pass)
3. Enters loop, checking every minute if an hourly task is due
4. At each hour's top (:00 seconds), executes the culling pipeline
5. Logs all results to `.openclaw_logs/scheduler.log`
6. Continues indefinitely until stopped (Ctrl+C)

#### Method 2: Background Daemon

```bash
nohup python run_openclaw_scheduler.py > openclaw.log 2>&1 &

# Or using screen
screen -S photo-scheduler -d -m python run_openclaw_scheduler.py
screen -r photo-scheduler  # to attach
```

#### Method 3: System Startup (macOS)

Create `~/Library/LaunchAgents/com.photo-automation.openclaw.plist` (see `.openclaw/README.md` for template)

```bash
launchctl load ~/Library/LaunchAgents/com.photo-automation.openclaw.plist
```

### Each Hour's Execution

When the scheduler triggers (every hour), it:

1. **Calls** `python main.py` with all configured thresholds
2. **Processes** all images in `./RAW/`
3. **Produces**:
   - `./CULLED/` — Best candidate images
   - `./REJECTED/` — Bad/redundant/excess images
   - `./cull_report.csv` — Audit report with decisions and reasons
4. **Logs** the execution result (success/failure) to `.openclaw_logs/`

### Monitoring OpenClaw Execution

**View scheduler logs:**
```bash
tail -f .openclaw_logs/scheduler.log
```

**Check workflow summary:**
```bash
cat .openclaw_logs/workflow_summary.json
```

**Verify latest results:**

### OpenClaw Components in This Project

**OpenClaw's Role:** OpenClaw is a workflow scheduling and orchestration framework (similar to Airflow or Prefect). It does **not** provide a native web dashboard or UI—it is purely for scheduling and executing tasks.

Here's what we're actually using from OpenClaw in this project:

1. **Workflow Definition** (`openclaw_scheduler.py`)
   - `Workflow` class to define the photo culling pipeline
   - `Task` definitions for the culling operation
   - Configuration of task parameters, timeouts, and error handling

2. **Scheduling** (`run_openclaw_scheduler.py`)
   - Uses Python's `schedule` library (compatible with OpenClaw patterns) for reliable hourly execution
   - Provides consistent job triggering at the top of each hour
   - Captures execution logs and handles failures

3. **Configuration** (`.openclaw/config.yaml`)
   - Centralized parameter storage for thresholds, paths, and timing
   - Makes the pipeline configurable without code changes

### 9) Photo Culling Web Dashboard (Custom Implementation)

**Note:** Since OpenClaw does not provide a UI, we built a custom Flask-based web dashboard to visualize scheduler jobs and culling results in real-time.

#### Dashboard Overview

**Type:** RESTful web application built with Flask and Jinja2 templates

**Purpose:** Provides a visual interface for monitoring the hourly photo culling workflow without needing to check logs or files manually.

#### Running the Dashboard

```bash
cd /Users/rmaski/Downloads/Photos-3-001/photo-automation
source ../.venv/bin/activate
pip install flask  # if not already installed
python dashboard.py
```

**Access:** Open browser to `http://localhost:5000`

#### Dashboard Components

The dashboard displays five main sections:

**1. Image Processing Summary**
- Count of images culled (kept for review)
- Count of images rejected (bad/redundant/excess)
- Total images processed across all runs

**2. Scheduler Status**
- Current status: running/idle/unknown
- Latest execution timestamp
- When scheduler was started
- Last recorded status message

**3. Recent Executions**
- List of last 10 hourly job runs
- Timestamp of each execution
- Success/failure status badge for each run
- Helps track job reliability over time

**4. Decision Summary**
- Breakdown of all decisions from the cull report
- Keep count vs Reject count
- Total images processed by the workflow

**5. Top Rejection Reasons (Visual Chart)**
- Bar chart of most common rejection reasons
- Examples: "blurry", "low_resolution", "overexposed", "daily_ranking_excess"
- Sorted by frequency with counts
- Helps identify quality issues in source photos

**6. Latest Cull Report Entries**
- Table of the most recent 50 processed images
- Filename, decision (keep/reject), reason, and quality score
- Color-coded decision badges (green=keep, red=reject)
- Useful for spot-checking individual decisions

#### Dashboard Features

- **Real-time Updates:** Reads from live scheduler logs and report files
- **No Database:** All data is pulled directly from:
  - `.openclaw_logs/scheduler.log` — Execution history
  - `./CULLED/` — Culled images folder
  - `./REJECTED/` — Rejected images folder
  - `./cull_report.csv` — Detailed audit report
- **API Endpoints:** Background data can be accessed via JSON API:
  - `/api/status` — Scheduler status
  - `/api/counts` — Image counts
  - `/api/report` — Cull report data
  - `/api/history` — Execution history

#### Running Scheduler and Dashboard Together

For integrated monitoring, run both in the background:

```bash
# Terminal 1: Start scheduler
cd /Users/rmaski/Downloads/Photos-3-001/photo-automation
source ../.venv/bin/activate
python run_openclaw_scheduler.py &

# Terminal 2: Start dashboard
cd /Users/rmaski/Downloads/Photos-3-001/photo-automation
source ../.venv/bin/activate
python dashboard.py
```

Then visit **http://localhost:5000** to monitor jobs as they run.
```bash
ls -lt CULLED/ REJECTED/  # Most recently processed
head -20 cull_report.csv  # Latest decisions
```

### Configuration Adjustments

Edit `.openclaw/config.yaml` to:

- **Change schedule**: Modify the interval (currently hourly execution at :00 seconds)
- **Adjust thresholds**: Modify `blur_threshold`, `duplicate_threshold`, `top_per_day`
- **Change paths**: Update `source`, `culled`, `rejected` directories
- **Error handling**: Adjust retry strategy and timeout settings

Restart scheduler after changes for them to take effect.

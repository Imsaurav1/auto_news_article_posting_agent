"""
scheduler.py — Runs the bot 5 times per day at fixed UTC times.

Schedule (UTC):
  06:00 — Morning run
  09:00 — Late morning
  12:00 — Noon
  15:00 — Afternoon
  18:00 — Evening

Usage:
  python scheduler.py          # runs forever (use screen/tmux/systemd/Render)
  python scheduler.py --now    # run once immediately (for testing)
"""

import sys
import time
import logging
import datetime
import subprocess
from pathlib import Path

Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SCHEDULER] %(message)s",
    handlers=[
        logging.FileHandler("logs/scheduler.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ── 5 daily run times (UTC) ───────────────────────────────────────────────────
RUN_TIMES = [
    "06:00",   # Morning
    "09:00",   # Late morning
    "12:00",   # Noon
    "15:00",   # Afternoon
    "18:00",   # Evening
]


def run_once():
    """Trigger main.py and wait for it to finish."""
    log.info("▶ Triggering main.py...")
    result = subprocess.run(["python", "main.py"], capture_output=False)
    if result.returncode == 0:
        log.info("✅ main.py finished successfully")
    else:
        log.error(f"❌ main.py exited with code {result.returncode}")


def run_scheduler():
    """Loop forever, firing main.py at each of the 5 configured times."""
    log.info("━" * 50)
    log.info("📅 TechNews Scheduler started")
    log.info(f"   Daily run times (UTC): {', '.join(RUN_TIMES)}")
    log.info("   Press Ctrl+C to stop")
    log.info("━" * 50)

    # Track which (date, time) combos have already run
    # Key: "YYYY-MM-DD HH:MM" — prevents double-firing within the same minute
    fired = set()

    while True:
        now       = datetime.datetime.utcnow()
        date_str  = now.strftime("%Y-%m-%d")
        time_str  = now.strftime("%H:%M")
        fire_key  = f"{date_str} {time_str}"

        if time_str in RUN_TIMES and fire_key not in fired:
            log.info(f"⏰ Scheduled run at {fire_key} UTC")
            fired.add(fire_key)

            # Clean up old keys (keep only today's) to avoid unbounded growth
            today_prefix = date_str
            fired = {k for k in fired if k.startswith(today_prefix)}

            run_once()

            # Print next run time for visibility
            upcoming = next_run_time(now)
            log.info(f"   Next run at: {upcoming} UTC")

        time.sleep(30)   # check every 30 seconds — low CPU, won't miss a minute


def next_run_time(now: datetime.datetime) -> str:
    """Return the next scheduled run time as a string."""
    current_hhmm = now.strftime("%H:%M")
    for t in RUN_TIMES:
        if t > current_hhmm:
            return t
    return RUN_TIMES[0] + " (tomorrow)"


if __name__ == "__main__":
    if "--now" in sys.argv:
        log.info("--now flag detected, running immediately")
        run_once()
    else:
        try:
            run_scheduler()
        except KeyboardInterrupt:
            log.info("Scheduler stopped.")
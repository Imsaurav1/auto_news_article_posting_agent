"""
scheduler.py — Runs the bot 5x/day AND binds a port so Render is happy.

Render Web Services require a port to be open or they mark the deploy as failed.
This file starts a tiny health-check HTTP server on $PORT (default 8080)
alongside the scheduler loop, so Render sees a live service.

Schedule (UTC):
  06:00 → Run 1 — Morning Briefing
  09:00 → Run 2 — AI Deep Dive
  12:00 → Run 3 — Tech Business Report
  15:00 → Run 4 — Automation & Future of Work
  18:00 → Run 5 — Science & Research Roundup
"""

import os
import sys
import time
import logging
import datetime
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
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

RUN_TIMES = ["06:00", "09:00", "11:00", "13:00", "15:00", "17:00", "21:00", "23:00", "02:00", "04:00"]  # UTC times for each run

# Track last run for health endpoint
last_run_info = {"time": "never", "status": "pending"}


# ── Tiny health-check server ──────────────────────────────────────────────────

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = (
            f"TechNews Bot — Running\n"
            f"Schedule: {', '.join(RUN_TIMES)} UTC\n"
            f"Last run: {last_run_info['time']} — {last_run_info['status']}\n"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # Silence default request logs to keep console clean
    def log_message(self, format, *args):
        pass


def start_health_server():
    """Start HTTP server on $PORT in a background thread."""
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    log.info(f"✅ Health server listening on port {port}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ── Scheduler loop ────────────────────────────────────────────────────────────

def run_once():
    """Run main.py as a subprocess."""
    log.info("▶ Running main.py...")
    last_run_info["time"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    result = subprocess.run(["python", "main.py"], capture_output=False)

    if result.returncode == 0:
        log.info("✅ main.py finished successfully")
        last_run_info["status"] = "success ✅"
    else:
        log.error(f"❌ main.py exited with code {result.returncode}")
        last_run_info["status"] = f"failed ❌ (code {result.returncode})"


def next_run_time(now: datetime.datetime) -> str:
    current = now.strftime("%H:%M")
    for t in RUN_TIMES:
        if t > current:
            return t
    return RUN_TIMES[0] + " (tomorrow)"


def run_scheduler():
    log.info("━" * 50)
    log.info("📅 TechNews Scheduler started")
    log.info(f"   Run times (UTC): {', '.join(RUN_TIMES)}")
    log.info("━" * 50)

    fired = set()

    while True:
        now      = datetime.datetime.now(datetime.timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")
        fire_key = f"{date_str} {time_str}"

        if time_str in RUN_TIMES and fire_key not in fired:
            log.info(f"⏰ Firing scheduled run at {fire_key} UTC")
            fired.add(fire_key)
            # Keep only today's fired keys
            fired = {k for k in fired if k.startswith(date_str)}
            run_once()
            log.info(f"   Next run at: {next_run_time(now)} UTC")

        time.sleep(30)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--now" in sys.argv:
        log.info("--now flag: running immediately")
        run_once()
    else:
        start_health_server()   # ← binds port so Render is happy
        try:
            run_scheduler()
        except KeyboardInterrupt:
            log.info("Scheduler stopped.")
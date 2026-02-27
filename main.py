#!/usr/bin/env python3
"""
TechNews Auto-Publisher
Runs 5x daily via scheduler.py.
Each run: Fetch → Generate → Publish to MongoDB → Update sitemap
"""

import json
import logging
import datetime
from pathlib import Path
from config import CONFIG
from fetcher import fetch_news
from generator import generate_article
from publisher import publish_article
from sitemap import generate_sitemap

Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/run.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


def load_todays_slugs() -> set:
    path  = Path("data/published.json")
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    if path.exists():
        data = json.loads(path.read_text())
        return set(data.get(today, []))
    return set()


def save_slug(slug: str):
    path  = Path("data/published.json")
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    Path("data").mkdir(exist_ok=True)

    data   = json.loads(path.read_text()) if path.exists() else {}
    cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    data   = {k: v for k, v in data.items() if k >= cutoff}

    data.setdefault(today, [])
    if slug not in data[today]:
        data[today].append(slug)
    path.write_text(json.dumps(data, indent=2))


def _run_number_today() -> int:
    hour = datetime.datetime.now(datetime.timezone.utc).hour
    if   hour <  6:  return 1
    elif hour <  8:  return 2
    elif hour < 10:  return 3
    elif hour < 12:  return 4
    elif hour < 14:  return 5
    elif hour < 16:  return 6
    elif hour < 18:  return 7
    elif hour < 20:  return 8
    elif hour < 22:  return 9
    else:            return 10

    
def run():
    now = datetime.datetime.now(datetime.timezone.utc)
    log.info("=" * 60)
    log.info(f"🚀 TechNews Bot — Run {_run_number_today()}/5")
    log.info(f"   {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    log.info("=" * 60)

    Path("data").mkdir(exist_ok=True)
    Path("output").mkdir(exist_ok=True)

    # ── 1. Fetch News ──────────────────────────────────────────────────────────
    log.info("📡 Step 1: Fetching latest news...")
    articles = fetch_news()
    if not articles:
        log.warning("No articles fetched. Exiting.")
        return
    log.info(f"   Found {len(articles)} relevant articles")

    # ── 2. Generate Article ────────────────────────────────────────────────────
    log.info("✍️  Step 2: Generating article via Groq...")
    result = generate_article(articles, run_number=_run_number_today())
    if not result:
        log.error("Article generation failed. Exiting.")
        return

    # ── 3. Publish to MongoDB ─────────────────────────────────────────────────
    log.info("🌐 Step 3: Publishing to MongoDB via /api/posts...")
    published_url = publish_article(result)
    if not published_url:
        log.error("Publishing failed. Exiting.")
        return

    log.info(f"   ✅ Live at: {published_url}")
    save_slug(result["slug"])

    # ── 4. Regenerate Sitemap ─────────────────────────────────────────────────
    log.info("🗺️  Step 4: Regenerating sitemap.xml...")
    generate_sitemap(new_slug=result["slug"])

    log.info("=" * 60)
    log.info(f"✅ Done! Run {_run_number_today()}/5 complete.")
    log.info("=" * 60)


if __name__ == "__main__":
    run()
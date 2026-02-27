#!/usr/bin/env python3
"""
TechNews Auto-Publisher
━━━━━━━━━━━━━━━━━━━━━━━
Fetches latest tech/AI/science news → generates article via Groq AI (Llama 3.3)
→ publishes to MongoDB via your existing /api/posts endpoint
→ regenerates sitemap.xml
→ pings Google + submits via IndexNow (no account/card needed)
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
from indexer import submit_to_google

# ── Logging ───────────────────────────────────────────────────────────────────
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


def load_published_slugs() -> set:
    path = Path("data/published.json")
    if path.exists():
        return set(json.loads(path.read_text()))
    return set()


def save_published_slug(slug: str):
    Path("data").mkdir(exist_ok=True)
    path = Path("data/published.json")
    slugs = load_published_slugs()
    slugs.add(slug)
    path.write_text(json.dumps(list(slugs), indent=2))


def run():
    log.info("=" * 60)
    log.info("🚀 TechNews Auto-Publisher — Daily Run")
    log.info(f"   {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    log.info("=" * 60)

    Path("data").mkdir(exist_ok=True)
    Path("output").mkdir(exist_ok=True)

    published = load_published_slugs()

    # ── 1. Fetch News ──────────────────────────────────────────────────────────
    log.info("📡 Step 1: Fetching latest news...")
    articles = fetch_news()
    if not articles:
        log.warning("No articles fetched. Exiting.")
        return
    log.info(f"   Found {len(articles)} relevant articles")

    # ── 2. Generate Article via Groq AI ───────────────────────────────────────
    log.info("✍️  Step 2: Generating article via Groq (llama-3.3-70b-versatile)...")
    result = generate_article(articles)
    if not result:
        log.error("Article generation failed. Exiting.")
        return

    slug = result["slug"]
    if slug in published:
        log.warning(f"Article '{slug}' already published today. Skipping.")
        return

    # ── 3. Publish to MongoDB ─────────────────────────────────────────────────
    log.info("🌐 Step 3: Publishing to MongoDB via /api/posts...")
    published_url = publish_article(result)
    if not published_url:
        log.error("Publishing failed. Exiting.")
        return

    log.info(f"   ✅ Live at: {published_url}")
    save_published_slug(slug)

    # ── 4. Regenerate Sitemap ─────────────────────────────────────────────────
    log.info("🗺️  Step 4: Regenerating sitemap.xml...")
    sitemap_path = generate_sitemap(new_slug=slug)
    log.info(
        f"   ✅ sitemap.xml saved to {sitemap_path}\n"
        f"   📋 Upload this file to your site root so it's live at:\n"
        f"      {CONFIG['site']['base_url']}/sitemap.xml"
    )

    # ── 5. Submit for Indexing ────────────────────────────────────────────────
    log.info("🔍 Step 5: Submitting to search engines...")
    submit_to_google(published_url)

    log.info("=" * 60)
    log.info("✅ All done!")
    log.info("=" * 60)


if __name__ == "__main__":
    run()
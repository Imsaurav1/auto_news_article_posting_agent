"""
indexer.py — Submits new URLs via IndexNow (Bing, Yandex, Seznam)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NOTE: Google Sitemap Ping was deprecated in 2023 (returns 404).
      Bing Sitemap Ping was also retired (returns 410).
      IndexNow is the modern replacement — covers Bing, Yandex, Seznam.
      Google discovers pages via IndexNow partners + your sitemap automatically.

No account, no credit card, no API keys needed.
One-time setup: host a small .txt key file on your website (instructions printed on first run).
"""

import uuid
import logging
import requests
from pathlib import Path
from config import CONFIG

log = logging.getLogger(__name__)

KEY_FILE = Path("data/indexnow_key.txt")


def get_or_create_indexnow_key() -> str:
    """Load existing IndexNow key or generate a new stable one."""
    KEY_FILE.parent.mkdir(exist_ok=True)

    if KEY_FILE.exists():
        key = KEY_FILE.read_text().strip()
        if key:
            return key

    key = uuid.uuid4().hex + uuid.uuid4().hex[:8]  # 40-char hex
    KEY_FILE.write_text(key)
    log.info(f"   🔑 New IndexNow key generated and saved to {KEY_FILE}")
    _print_setup_instructions(key)
    return key


def _print_setup_instructions(key: str):
    base_url = CONFIG["site"]["base_url"].rstrip("/")
    log.info("")
    log.info("━" * 60)
    log.info("  ONE-TIME INDEXNOW SETUP (do this once)")
    log.info("━" * 60)
    log.info(f"  1. Create a file named : {key}.txt")
    log.info(f"  2. File contents       : {key}")
    log.info(f"  3. Host it at          : {base_url}/{key}.txt")
    log.info(f"     (Visiting that URL should show just the key text)")
    log.info(f"  4. Done — no signup or verification needed.")
    log.info("━" * 60)
    log.info("")


def submit_indexnow(url: str) -> bool:
    """
    Submit URL via IndexNow — notifies Bing, Yandex, Seznam instantly.
    Google picks up new content via IndexNow partners + your sitemap.
    """
    cfg      = CONFIG["site"]
    base_url = cfg["base_url"].rstrip("/")
    key      = get_or_create_indexnow_key()
    key_url  = f"{base_url}/{key}.txt"

    payload = {
        "host":        base_url.replace("https://", "").replace("http://", ""),
        "key":         key,
        "keyLocation": key_url,
        "urlList":     [url],
    }

    try:
        resp = requests.post(
            "https://api.indexnow.org/indexnow",
            json=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=15,
        )

        if resp.status_code in (200, 202):
            log.info(f"   ✅ IndexNow accepted (HTTP {resp.status_code})")
            log.info(f"      Notified: Bing, Yandex, Seznam + IndexNow network")
            return True
        elif resp.status_code == 403:
            log.warning(
                f"   ⚠️  IndexNow: key file not found (HTTP 403)\n"
                f"      Host the key file at: {key_url}\n"
                f"      File content must be exactly: {key}"
            )
            return False
        elif resp.status_code == 422:
            log.warning("   ⚠️  IndexNow: URL/host mismatch — check site.base_url in config.py")
            return False
        else:
            log.warning(f"   ⚠️  IndexNow: HTTP {resp.status_code} — {resp.text[:150]}")
            return False

    except requests.exceptions.Timeout:
        log.warning("   ⚠️  IndexNow: request timed out")
        return False
    except Exception as e:
        log.warning(f"   ⚠️  IndexNow error: {e}")
        return False


def submit_to_google(url: str) -> bool:
    """
    Main indexing entry point called from main.py.
    Only uses IndexNow — Google/Bing sitemap pings are deprecated.
    """
    log.info(f"   Submitting: {url}")
    result = submit_indexnow(url)

    if result:
        log.info("   Indexing summary: IndexNow=✅  (Google/Bing pings deprecated — removed)")
    else:
        log.warning("   Indexing summary: IndexNow=❌  (check key file setup)")

    return result
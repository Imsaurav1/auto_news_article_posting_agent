"""
generator.py — Sends news to Groq AI (llama-3.3-70b-versatile) and generates article
"""

import re
import json
import logging
import datetime
import requests
from config import CONFIG

log = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Convert title to URL-safe slug (mirrors your backend's slugify logic)."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text[:80]


def build_prompt(articles: list[dict]) -> str:
    """Build the prompt for Llama with today's news data."""
    today = datetime.datetime.now().strftime("%B %d, %Y")

    news_block = ""
    for i, art in enumerate(articles[:15], 1):
        news_block += f"""
Article {i}:
  Title: {art['title']}
  Source: {art['source']}
  Summary: {art['summary'][:300]}
  URL: {art['url']}
"""

    return f"""You are a professional tech journalist writing for a popular technology blog.

Today is {today}. I have gathered the following latest news articles from tech/AI/science sources:

{news_block}

Based on these real news items, write a comprehensive, engaging tech news article.

Return your response as a valid JSON object. No markdown, no code fences, no explanation — ONLY raw JSON.

Use this exact structure:
{{
  "title": "Specific headline referencing the actual top story (max 70 chars)",
  "excerpt": "2-sentence summary mentioning the specific topics covered (max 200 chars)",
  "meta_keywords": "8-12 comma-separated keywords",
  "tags": ["AI", "Technology", "Automation"],
  "reading_time": 5,
  "content": "<h2>Introduction</h2><p>...</p>",
  "sources": [
    {{"name": "Source Name", "url": "https://..."}}
  ]
}}

CRITICAL REQUIREMENTS for title:
- NEVER use generic titles like "Tech News Roundup" or "Weekly Digest"
- MUST reference a specific technology, company, product, or trend from today's articles
- Good examples: "OpenAI's New Model Challenges Google as AI Race Heats Up"
                  "Llama 4 Leaked: Meta's Next AI Model Could Rival GPT-5"
                  "Cybersecurity Breaches Surge as AI-Powered Attacks Hit Record High"
- The title should make someone curious enough to click

REQUIREMENTS for content field:
- Write 800-1200 words of ORIGINAL content (not copied from sources)
- Use proper HTML tags only: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>
- Start with a strong intro paragraph referencing today's biggest story
- Cover 3-5 major stories from the news items above with a <h2> for each
- Include a "Key Takeaways" section near the end
- End with a brief forward-looking conclusion
- NO <html>, <head>, <body>, or <script> wrapper tags
- Synthesize and add your own analysis — do not plagiarize

RETURN ONLY THE RAW JSON. No text before or after it."""


def call_groq(prompt: str) -> str | None:
    """Call the Groq API and return the raw response text."""
    cfg = CONFIG["groq"]

    if "YOUR_" in cfg["api_key"]:
        log.error("Groq API key not configured in config.py or environment variables.")
        return None

    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": cfg["model"],
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a professional tech journalist. "
                    "Always respond with only valid raw JSON — no markdown, "
                    "no code fences, no preamble."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": cfg["max_tokens"],
        "temperature": cfg["temperature"],
        "response_format": {"type": "json_object"},  # Forces JSON output
    }

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    except requests.exceptions.Timeout:
        log.error("Groq API request timed out after 60s")
        return None
    except requests.exceptions.HTTPError as e:
        log.error(f"Groq API HTTP error: {e.response.status_code} — {e.response.text[:300]}")
        return None
    except Exception as e:
        log.error(f"Groq API call failed: {e}")
        return None


def generate_article(articles: list[dict]) -> dict | None:
    """
    Generate a full article from news data using Groq AI.
    Returns a dict ready to POST to your /api/posts endpoint.
    """
    cfg_groq    = CONFIG["groq"]
    cfg_article = CONFIG["article"]
    cfg_site    = CONFIG["site"]

    log.info(f"   Calling Groq ({cfg_groq['model']}) with {len(articles)} articles...")

    prompt = build_prompt(articles)
    raw    = call_groq(prompt)

    if not raw:
        return None

    # Strip accidental markdown fences (safety net even with response_format)
    raw = re.sub(r"^```json\s*", "", raw.strip())
    raw = re.sub(r"^```\s*",     "", raw)
    raw = re.sub(r"\s*```$",     "", raw)
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.error(f"Failed to parse Groq JSON response: {e}")
        log.debug(f"Raw response (first 500 chars): {raw[:500]}")
        return None

    # ── Validate required fields ───────────────────────────────────────────────
    for field in ["title", "content", "excerpt"]:
        if not data.get(field):
            log.error(f"Groq response missing required field: '{field}'")
            return None

    # ── Append sources block to content HTML ───────────────────────────────────
    sources = data.get("sources", [])
    if cfg_article["include_sources"] and sources:
        # Also include raw fetched article URLs
        seen = {s["url"] for s in sources}
        for art in articles[:8]:
            if art["url"] and art["url"] not in seen:
                sources.append({"name": art["source"], "url": art["url"]})
                seen.add(art["url"])

        source_items = "\n".join(
            f'<li><a href="{s["url"]}" target="_blank" rel="noopener noreferrer">'
            f'{s["name"]}</a></li>'
            for s in sources if s.get("url")
        )
        data["content"] += f"""
<hr/>
<h3>📰 Sources &amp; References</h3>
<ul>
{source_items}
</ul>"""

    # ── Build the final payload matching your PostSchema exactly ───────────────
    today       = datetime.datetime.now().strftime("%Y-%m-%d")
    slug        = slugify(data["title"])
    tags        = data.get("tags", cfg_article["default_tags"])
    # Merge default tags with AI-generated tags, remove duplicates
    merged_tags = list(dict.fromkeys(cfg_article["default_tags"] + tags))

    result = {
        # PostSchema fields
        "title":         data["title"],
        "slug":          slug,                        # your backend deduplicates this
        "content":       data["content"],
        "excerpt":       data.get("excerpt", "")[:300],
        "featuredImage": "",                          # can be set later manually
        "status":        "published",
        "author":        "TechNews Bot",
        "tags":          merged_tags,

        # Extra metadata for logging / Google indexing
        "_meta": {
            "date":           today,
            "reading_time":   data.get("reading_time", 5),
            "meta_keywords":  data.get("meta_keywords", ""),
            "canonical_url":  f"{cfg_site['base_url']}/blog/{slug}",
        }
    }

    log.info(f"   ✅ Article ready: '{data['title']}'")
    log.info(f"   Slug: {slug} | Tags: {merged_tags}")
    return result
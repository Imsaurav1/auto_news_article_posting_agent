"""
generator.py — Sends news to Groq AI (llama-3.3-70b-versatile) and generates article
Supports 5 different daily angles so each of the 5 runs produces a unique article.
"""

import re
import json
import logging
import datetime
import requests
from config import CONFIG

log = logging.getLogger(__name__)


# ── Each run covers a different angle so all 5 daily articles are unique ──────
RUN_ANGLES = {
    1: {
        "focus":   "the biggest breaking tech/AI story of the morning",
        "style":   "urgent and informative — what just happened and why it matters now",
        "label":   "Morning Tech Briefing",
    },
    2: {
        "focus":   "AI and machine learning developments specifically",
        "style":   "analytical — explain the technology and its real-world impact in depth",
        "label":   "AI Deep Dive",
    },
    3: {
        "focus":   "business and industry impact — funding, acquisitions, market shifts",
        "style":   "business-focused — who gains, who loses, what investors should watch",
        "label":   "Tech Business Report",
    },
    4: {
        "focus":   "automation, robotics, and the future of work",
        "style":   "forward-looking — what these developments mean for workers and society",
        "label":   "Automation & Future of Work",
    },
    5: {
        "focus":   "science breakthroughs and emerging technologies",
        "style":   "educational — explain complex research in clear, accessible language",
        "label":   "Science & Research Roundup",
    },
}


def slugify(text: str) -> str:
    """Convert title to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text[:80]


def build_prompt(articles: list[dict], run_number: int = 1) -> str:
    """Build the Groq prompt, varying angle by run number (1–5)."""
    today  = datetime.datetime.now().strftime("%B %d, %Y")
    angle  = RUN_ANGLES.get(run_number, RUN_ANGLES[1])

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

Today is {today}. This is article #{run_number} of 5 for today.

TODAY'S FOCUS: {angle['focus']}
WRITING STYLE: {angle['style']}
SECTION LABEL: {angle['label']}

Here are the latest news articles to draw from:
{news_block}

Write an original article focused specifically on: {angle['focus']}

Return ONLY a raw JSON object with this exact structure (no markdown, no code fences):
{{
  "title": "Specific headline about {angle['focus']} (max 70 chars)",
  "excerpt": "2-sentence summary highlighting the specific angle covered (max 200 chars)",
  "meta_keywords": "8-12 comma-separated keywords relevant to this article",
  "tags": ["AI", "Technology"],
  "reading_time": 5,
  "content": "<h2>...</h2><p>...</p>",
  "sources": [
    {{"name": "Source Name", "url": "https://..."}}
  ]
}}

CRITICAL — title rules:
- NEVER use "Tech News Roundup", "Weekly Digest", or any generic title
- MUST reference a specific company, product, technology, or person from the articles
- Should be written as a compelling news headline that makes people want to click
- Good example: "Nvidia's New AI Chip Threatens Intel's Data Center Dominance"

REQUIREMENTS for content:
- 800-1200 words of ORIGINAL writing
- HTML tags only: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>
- Open with a strong hook tied to today's biggest story in this angle
- Cover 3-5 stories with a <h2> heading for each
- Include a "Key Takeaways" <h2> section near the end
- Close with a forward-looking conclusion paragraph
- NO <html>, <head>, <body>, <script> tags
- Analyze and synthesize — do not copy text from sources

RETURN ONLY THE RAW JSON OBJECT."""


def call_groq(prompt: str) -> str | None:
    """Call the Groq API."""
    cfg = CONFIG["groq"]

    if "YOUR_" in cfg["api_key"]:
        log.error("Groq API key not set in config.py")
        return None

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type":  "application/json",
            },
            json={
                "model": cfg["model"],
                "messages": [
                    {
                        "role":    "system",
                        "content": "You are a professional tech journalist. Always respond with only valid raw JSON — no markdown, no code fences, no preamble."
                    },
                    {
                        "role":    "user",
                        "content": prompt
                    }
                ],
                "max_tokens":      cfg["max_tokens"],
                "temperature":     cfg["temperature"],
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    except requests.exceptions.Timeout:
        log.error("Groq API timed out after 60s")
        return None
    except requests.exceptions.HTTPError as e:
        log.error(f"Groq HTTP error: {e.response.status_code} — {e.response.text[:300]}")
        return None
    except Exception as e:
        log.error(f"Groq call failed: {e}")
        return None


def generate_article(articles: list[dict], run_number: int = 1) -> dict | None:
    """
    Generate article via Groq. run_number (1-5) controls the angle/focus.
    Returns a dict ready to POST to your /api/posts endpoint.
    """
    cfg_article = CONFIG["article"]
    cfg_site    = CONFIG["site"]
    angle       = RUN_ANGLES.get(run_number, RUN_ANGLES[1])

    log.info(f"   Run {run_number}/5 — Angle: {angle['label']}")

    raw = call_groq(build_prompt(articles, run_number))
    if not raw:
        return None

    # Strip accidental markdown fences
    raw = re.sub(r"^```json\s*", "", raw.strip())
    raw = re.sub(r"^```\s*",     "", raw)
    raw = re.sub(r"\s*```$",     "", raw)

    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError as e:
        log.error(f"Failed to parse Groq JSON: {e}")
        log.debug(f"Raw (first 500): {raw[:500]}")
        return None

    for field in ["title", "content", "excerpt"]:
        if not data.get(field):
            log.error(f"Missing required field: '{field}'")
            return None

    # Append sources to content HTML
    sources = data.get("sources", [])
    if cfg_article["include_sources"] and sources:
        seen = {s["url"] for s in sources}
        for art in articles[:8]:
            if art["url"] and art["url"] not in seen:
                sources.append({"name": art["source"], "url": art["url"]})
                seen.add(art["url"])

        items = "\n".join(
            f'<li><a href="{s["url"]}" target="_blank" rel="noopener">{s["name"]}</a></li>'
            for s in sources if s.get("url")
        )
        data["content"] += f"\n<hr/>\n<h3>📰 Sources</h3>\n<ul>\n{items}\n</ul>"

    # Build tags
    ai_tags     = data.get("tags", [])
    merged_tags = list(dict.fromkeys(cfg_article["default_tags"] + ai_tags))

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    slug  = slugify(data["title"])

    result = {
        "title":         data["title"],
        "slug":          slug,
        "content":       data["content"],
        "excerpt":       data.get("excerpt", "")[:300],
        "featuredImage": "",
        "status":        "published",
        "author":        "TechNews Bot",
        "tags":          merged_tags,
        "_meta": {
            "date":          today,
            "run_number":    run_number,
            "angle":         angle["label"],
            "reading_time":  data.get("reading_time", 5),
            "meta_keywords": data.get("meta_keywords", ""),
            "canonical_url": f"{cfg_site['base_url']}/blog/{slug}",
        }
    }

    log.info(f"   ✅ '{data['title']}'")
    log.info(f"   Slug: {slug} | Tags: {merged_tags}")
    return result
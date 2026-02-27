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
    6: {
        "focus":   "cybersecurity threats, data breaches, and privacy news",
        "style":   "cautionary — explain risks and what users/companies should do",
        "label":   "Cybersecurity Watch",
    },
    7: {
        "focus":   "startup ecosystem — new launches, funding rounds, acquisitions",
        "style":   "exciting and entrepreneurial — who's disrupting what",
        "label":   "Startup & VC Report",
    },
    8: {
        "focus":   "consumer tech — gadgets, apps, phones, wearables",
        "style":   "accessible and enthusiastic — written for everyday tech users",
        "label":   "Consumer Tech Update",
    },
    9: {
        "focus":   "cloud computing, developer tools, and open source news",
        "style":   "technical but clear — written for developers and engineers",
        "label":   "Dev & Cloud Digest",
    },
    10: {
        "focus":   "global tech policy, regulation, and big tech controversies",
        "style":   "balanced and analytical — cover multiple perspectives",
        "label":   "Tech Policy & Regulation",
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
    """Build the Groq prompt, varying angle by run number."""
    today  = datetime.datetime.now().strftime("%B %d, %Y")
    angle  = RUN_ANGLES.get(run_number, RUN_ANGLES[1])

    news_block = ""
    for i, art in enumerate(articles[:15], 1):
        news_block += f"""
Article {i}:
  Title: {art['title']}
  Source: {art['source']}
  Summary: {art['summary'][:500]}
  URL: {art['url']}
"""

    return f"""You are a news reporter writing for a tech news website. Today is {today}.

Your job is to REPORT the actual news stories below — like a journalist, not a blogger.
This article's focus: {angle['focus']}

NEWS ARTICLES TO REPORT ON:
{news_block}

STRICT RULES — read carefully:

1. REPORT THE ACTUAL NEWS — Every paragraph must be about something that actually happened in the articles above.
   - Use real names: companies, people, products, numbers mentioned in the articles
   - Example GOOD: "Jack Dorsey's Block announced it is cutting 40% of its workforce, citing AI automation as the reason."
   - Example BAD: "Many companies are using AI to reduce costs." (too vague, not from the news)

2. NO GENERIC AI FILLER — Do NOT write these kinds of sentences:
   - "This raises important questions about the future of work"
   - "Experts predict that automation will continue to grow"
   - "It remains to be seen how this will impact the industry"
   - "This is a significant development in the world of technology"
   - Any sentence that could appear in ANY article regardless of the news

3. REWRITE IN YOUR OWN WORDS — Do not copy sentences from the summaries.
   Rephrase the actual facts naturally, like a human journalist would.
   Use a conversational but professional tone — short sentences, active voice.

4. STRUCTURE — Each <h2> section must cover ONE specific news story:
   - Start directly with what happened: who, what, when, where
   - Give the key facts and numbers from that story
   - One short paragraph on why it matters — based on facts in the article, not opinion
   - Do NOT end with "only time will tell" or "the future is uncertain" type phrases

5. OPENING PARAGRAPH — Start with the most interesting/surprising fact from the news, not a general statement.
   - BAD: "The technology industry has been seeing major changes lately."
   - GOOD: "Block just eliminated 1,748 jobs in a single announcement — and its CEO says AI is why."

Return ONLY a raw JSON object (no markdown, no code fences):
{{
  "title": "Headline using a real fact, name, or number from today's news (max 70 chars)",
  "excerpt": "2 sentences summarizing the actual news covered, with specific details (max 200 chars)",
  "meta_keywords": "8-12 comma-separated keywords from the actual stories",
  "tags": ["AI", "Technology"],
  "reading_time": 5,
  "content": "<p>Opening with the most surprising fact...</p><h2>Story 1 headline</h2><p>...</p>",
  "sources": [
    {{"name": "Source Name", "url": "https://..."}}
  ]
}}

TITLE RULES:
- Must contain a real name, company, number, or product from today's articles
- NEVER: "Tech Roundup", "AI News", "This Week in Tech", or any generic title
- GOOD: "Block Cuts 1,748 Jobs as Dorsey Bets on AI Over Headcount"
- GOOD: "Nvidia Hits $3T Valuation as Jensen Huang Dismisses Rivals"

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
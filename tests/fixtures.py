"""Fictional sample data for offline tests and the demo preview (not real news)."""
from datetime import datetime, timedelta, timezone

NOW = datetime(2026, 11, 21, 0, 30, tzinfo=timezone.utc)


def rss(items):
    entries = "".join(
        f"<item><title>{t}</title><link>{u}</link><description>{s}</description>"
        f"<pubDate>{(NOW - timedelta(hours=h)).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate></item>"
        for t, u, s, h in items
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>{entries}</channel></rss>'


NEWS_FEED = rss([
    ("Acme Cloud postmortem: how a retry storm took down login for 3 hours",
     "https://example.com/acme-postmortem?utm_source=rss",
     "A config push caused timeouts; clients retried without backoff and overloaded the auth service.", 3),
    ("Acme Cloud postmortem: retry storm took down login",          # near-duplicate
     "https://example.org/acme-retry", "Same story, different outlet.", 5),
    ("Black Friday deal: 40% off mechanical keyboards",            # blocked topic
     "https://example.com/deal", "Huge discount.", 2),
    ("Widget.js 5.0 ships server components by default",
     "https://example.com/widget5", "The new major version changes the default rendering model.", 8),
    ("Old news from last week", "https://example.com/old", "stale", 200),
])

BLOG_FEED = rss([
    ("Designing a rate limiter that survives 10x traffic spikes",
     "https://blog.example.com/rate-limiter", "Token bucket vs sliding window, with production numbers.", 10),
])

SECURITY_FEED = rss([
    ("Malicious npm package mimics popular logging library, steals CI secrets",
     "https://sec.example.com/npm-typosquat", "Typosquatted package exfiltrates environment variables in postinstall.", 6),
])

CFG = {
    "profile": {"who": "test engineer", "interests": {"backend": 3},
                "avoid": ["deal", "discount"]},
    "digest": {"timezone": "Asia/Kolkata", "lookback_hours": 30, "max_items": 8, "min_score": 6,
               "candidates_for_llm": 70, "hn_min_points": 100,
               "sections": ["top_story", "headlines", "deep_read", "security", "release_radar"]},
    "delivery": {"email": True, "push": True, "site_url": "https://you.github.io/devbrief"},
    "llm": {"provider": "auto"},
    "sources": [], "release_radar": [],
}

SRC = {
    "news": {"name": "Example News", "kind": "news", "weight": 1.0},
    "blog": {"name": "Example Eng Blog", "kind": "blog", "weight": 1.3},
    "security": {"name": "Example Sec", "kind": "security", "weight": 1.0},
}


def fake_llm_response(cands):
    idx = {c.title: i for i, c in enumerate(cands)}
    def find(prefix):
        return next(i for t, i in idx.items() if t.startswith(prefix))
    return {
        "tldr": "A retry storm postmortem and a supply-chain attack are both reminders that resilience and dependency hygiene matter.",
        "items": [
            {"id": find("Acme Cloud postmortem"), "section": "top_story", "score": 9,
             "one_liner": "A config push slowed auth; clients retried with no backoff and turned a blip into a 3-hour outage.",
             "why_read": "Textbook retry-storm failure — exactly the 'what can go wrong' story interviewers love in system design rounds.",
             "tags": ["outage", "resilience"], "read_minutes": 8,
             "takeaways": ["A config push caused timeouts in the auth service", "Clients retried without backoff, multiplying load", "Login was down for about 3 hours"],
             "context": "Auth services sit on every request path, so when they slow down, every client feels it at once."},
            {"id": find("Malicious npm"), "section": "security", "score": 8,
             "one_liner": "A typosquatted npm package steals CI secrets during postinstall.",
             "why_read": "If you use Node, check your lockfile today and learn why install scripts are a supply-chain risk.",
             "tags": ["security", "npm"], "read_minutes": 4,
             "takeaways": ["Package name imitates a popular logging library", "Steals environment variables during postinstall"],
             "context": "npm runs install scripts automatically, so a malicious package can execute code on your machine or CI runner."},
            {"id": find("Designing a rate limiter"), "section": "deep_read", "score": 8,
             "one_liner": "Token bucket vs sliding-window limiters compared with real production numbers.",
             "why_read": "Rate limiters are a top-5 system design question; this gives you real trade-offs to quote.",
             "tags": ["system-design", "resilience"], "read_minutes": 14,
             "takeaways": ["Compares token bucket and sliding-window algorithms", "Includes numbers from production traffic"],
             "context": "A rate limiter caps how many requests a client can make in a time window to protect a service."},
            {"id": find("Widget.js 5.0"), "section": "headlines", "score": 7,
             "one_liner": "The new major version renders on the server by default.",
             "why_read": "Shifts how you structure data fetching in frontend projects.",
             "tags": ["web"], "read_minutes": 5},
            {"id": 999, "section": "headlines", "score": 10, "one_liner": "hallucinated", "why_read": "x"},
        ],
        "concept": {"name": "Exponential backoff with jitter",
                    "explanation": "When a call fails, wait longer before each retry and add randomness so thousands of clients don't retry in sync. It turns a thundering herd into a gentle trickle.",
                    "interview_question": "Why does adding jitter to retries prevent cascading failures?",
                    "related_item_id": find("Acme Cloud postmortem")},
        "glossary": [{"term": "Retry storm", "meaning": "Clients retrying failures so aggressively that they cause more failures."},
                     {"term": "Typosquatting", "meaning": "Publishing a package named like a popular one to trick installers."}],
        "quiz": [
            {"question": "What turned a short auth slowdown into a 3-hour outage at Acme Cloud?",
             "options": ["A database migration", "Clients retrying without backoff", "An expired TLS certificate", "A DDoS attack"],
             "answer": 1, "explanation": "Clients retried immediately and repeatedly, overloading the auth service further.",
             "item_id": find("Acme Cloud postmortem")},
            {"question": "When does the malicious npm package steal secrets?",
             "options": ["At import time", "During postinstall", "When tests run", "On publish"],
             "answer": 1, "explanation": "It runs during the postinstall script, which npm executes automatically.",
             "item_id": find("Malicious npm")},
            {"question": "Broken question with duplicate options", "options": ["a", "a", "b", "c"], "answer": 0},
            {"question": "Which rate limiter allows short bursts up to a fixed capacity?",
             "options": ["Token bucket", "Fixed window", "Leaky pipe", "Round robin"],
             "answer": 0, "explanation": "Tokens accumulate up to the bucket size, so short bursts are allowed.", "item_id": 999},
        ],
    }

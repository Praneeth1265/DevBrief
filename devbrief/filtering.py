"""Cheap, deterministic filtering before anything reaches the LLM."""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from .models import Item

_WORD = re.compile(r"[a-z0-9]+")
_STOP = set("a an the of to in for on and or with is are was be by at from as how why what "
            "your you we our new now its it this that vs via about into".split())

# Keywords → which interest bucket they hint at (used by the heuristic scorer only).
HINTS = {
    "system design": ["architecture", "scal", "distributed", "microservice", "latency", "cache",
                      "database", "postgres", "kafka", "queue", "sharding", "consensus"],
    "backend": ["api", "backend", "server", "rust", "go ", "golang", "java", "node", "python"],
    "ai": ["llm", "ai ", "agent", "model", "gpt", "claude", "gemini", "inference", "rag", "mcp"],
    "web": ["react", "next.js", "nextjs", "typescript", "javascript", "css", "browser", "web"],
    "cloud": ["aws", "kubernetes", "k8s", "docker", "cloud", "serverless", "terraform", "ci/cd"],
    "security": ["vulnerab", "cve", "breach", "exploit", "ransomware", "zero-day", "supply chain",
                 "malicious package", "npm", "pypi"],
    "industry": ["layoff", "hiring", "tcs", "infosys", "wipro", "hcl", "campus", "placement",
                 "salary", "freshers", "gcc"],
    "outage": ["outage", "postmortem", "post-mortem", "incident", "downtime"],
}


def tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


def similar(a: str, b: str, threshold: float = 0.6) -> bool:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / min(len(ta), len(tb)) >= threshold


def is_blocked(item: Item, avoid: list[str]) -> bool:
    hay = f"{item.title} {item.summary[:200]}".lower()
    return any(a.lower() in hay for a in avoid)


def heuristic_score(item: Item, now: datetime) -> float:
    """0-10 rough relevance: source quality, topic hints, community votes, freshness."""
    hay = f" {item.title} {item.summary} ".lower()
    topical = sum(1 for words in HINTS.values() if any(w in hay for w in words))
    score = 3.0 * item.weight + min(topical, 3) * 1.0
    if item.points:
        score += min(math.log10(max(item.points, 1)) * 1.2, 3.0)
    age_h = (now - item.published).total_seconds() / 3600
    score -= max(age_h - 12, 0) * 0.04
    if item.kind == "release":
        score -= 0.5
    return round(max(0.0, min(score, 10.0)), 2)


def prefilter(items: list[Item], cfg: dict, seen: set[str], now: datetime | None = None) -> tuple[list[Item], dict]:
    now = now or datetime.now(timezone.utc)
    d = cfg["digest"]
    since = now - timedelta(hours=d["lookback_hours"])
    avoid = cfg["profile"].get("avoid", [])
    stats = Counter(fetched=len(items))

    kept: list[Item] = []
    keys: set[str] = set()
    for it in sorted(items, key=lambda i: (i.points, i.weight), reverse=True):
        if it.published < since:
            stats["too_old"] += 1; continue
        if it.key in seen:
            stats["already_sent"] += 1; continue
        if is_blocked(it, avoid):
            stats["blocked_topic"] += 1; continue
        if it.key in keys or any(similar(it.title, k.title) for k in kept):
            stats["duplicate"] += 1; continue
        keys.add(it.key)
        it.score = heuristic_score(it, now)
        kept.append(it)

    kept.sort(key=lambda i: i.score, reverse=True)
    # Diversity: no single source may flood the candidate pool.
    per_source: Counter = Counter()
    pool = []
    for it in kept:
        if per_source[it.source] >= 8:
            continue
        per_source[it.source] += 1
        pool.append(it)
    pool = pool[: d["candidates_for_llm"]]
    stats["candidates"] = len(pool)
    return pool, dict(stats)

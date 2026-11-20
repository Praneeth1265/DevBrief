"""Fetch candidate items from RSS/Atom feeds, Hacker News and GitHub releases."""
from __future__ import annotations

import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from time import mktime

import feedparser
import requests

from .models import Item

log = logging.getLogger("devbrief.sources")
UA = "DevBrief/1.0 (+https://github.com/; personal news digest)"
TIMEOUT = 20
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_PRERELEASE = re.compile(r"\b(rc|alpha|beta|nightly|canary|preview|pre)\b|-rc|\d(a|b)\d", re.I)


def clean_text(raw: str, limit: int = 400) -> str:
    text = _WS.sub(" ", html.unescape(_TAG.sub(" ", raw or ""))).strip()
    return text[:limit].rsplit(" ", 1)[0] + "…" if len(text) > limit else text


def _entry_time(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        t = entry.get(attr)
        if t:
            return datetime.fromtimestamp(mktime(t), tz=timezone.utc)
    return None


def parse_feed(content: bytes | str, src: dict) -> list[Item]:
    feed = feedparser.parse(content)
    items = []
    for e in feed.entries[:60]:
        link, title = e.get("link"), clean_text(e.get("title", ""), 300)
        published = _entry_time(e)
        if not (link and title and published):
            continue
        summary = e.get("summary") or (e.get("content") or [{}])[0].get("value", "")
        items.append(Item(
            title=title, url=link, source=src["name"], kind=src.get("kind", "news"),
            published=published, summary=clean_text(summary), weight=src.get("weight", 1.0),
        ))
    return items


def fetch_feed(src: dict) -> list[Item]:
    try:
        r = requests.get(src["url"], headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        items = parse_feed(r.content, src)
        log.info("%-22s %3d items", src["name"], len(items))
        return items
    except Exception as exc:  # one bad feed must never kill the digest
        log.warning("%-22s FAILED: %s", src["name"], exc)
        return []


def fetch_hn(src: dict, min_points: int, since: datetime) -> list[Item]:
    """Hacker News stories above a points threshold, via the Algolia API."""
    url = "https://hn.algolia.com/api/v1/search"
    params = {
        "tags": "story",
        "numericFilters": f"points>={min_points},created_at_i>={int(since.timestamp())}",
        "hitsPerPage": 60,
    }
    try:
        r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        hits = r.json().get("hits", [])
    except Exception as exc:
        log.warning("Hacker News FAILED: %s", exc)
        return []
    items = []
    for h in hits:
        hn_url = f"https://news.ycombinator.com/item?id={h['objectID']}"
        items.append(Item(
            title=h.get("title", ""), url=h.get("url") or hn_url, source="Hacker News",
            kind=src.get("kind", "aggregator"), weight=src.get("weight", 1.0),
            published=datetime.fromtimestamp(h["created_at_i"], tz=timezone.utc),
            summary=clean_text(h.get("story_text") or ""), points=h.get("points", 0),
            comments_url=hn_url,
        ))
    log.info("%-22s %3d items", "Hacker News", len(items))
    return items


def fetch_releases(repo: str) -> list[Item]:
    src = {"name": f"GitHub · {repo}", "kind": "release", "weight": 1.0,
           "url": f"https://github.com/{repo}/releases.atom"}
    items = [i for i in fetch_feed(src) if not _PRERELEASE.search(i.title)]
    for i in items:
        i.title = f"{repo.split('/')[-1]} {i.title}" if repo.split("/")[-1].lower() not in i.title.lower() else i.title
    return items


def fetch_all(cfg: dict, now: datetime | None = None) -> list[Item]:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=cfg["digest"]["lookback_hours"])
    jobs = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        for src in cfg["sources"]:
            if src.get("type") == "hn":
                jobs.append(pool.submit(fetch_hn, src, cfg["digest"]["hn_min_points"], since))
            else:
                jobs.append(pool.submit(fetch_feed, src))
        for repo in cfg.get("release_radar", []):
            jobs.append(pool.submit(fetch_releases, repo))
        items = [i for j in jobs for i in j.result()]
    return items

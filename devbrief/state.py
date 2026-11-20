"""Persistence: 'already sent' memory + the JSON API the mobile app reads (committed by CI).

docs/                       ← served by GitHub Pages = the app
  index.html, app.js, sw.js …   (the app itself, static)
  api/index.json            list of all briefs (newest first)
  api/digests/<name>.json   one brief
  api/learn.json            every Interview-angle concept + glossary term so far
  api/topics.json           stories grouped by tag + what's trending this week
  api/config.json           public settings for the app (VAPID public key)
"""
from __future__ import annotations

import json
import os
from datetime import date as Date, timedelta
from pathlib import Path

from .models import Digest
from .render import pretty

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"
API = DOCS / "api"
SEEN = DATA / "seen.json"


def load_seen() -> dict[str, str]:
    return json.loads(SEEN.read_text()) if SEEN.exists() else {}


def save_seen(seen: dict[str, str], today: str, keep_days: int = 45) -> None:
    cutoff = (Date.fromisoformat(today) - timedelta(days=keep_days)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    DATA.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(seen, indent=0, sort_keys=True))


def _dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False))


def save_digest(digest: Digest, name: str | None = None, heading: str | None = None) -> str:
    name = name or digest.date
    payload = digest.to_dict() | {"name": name, "heading": heading or pretty(digest.date),
                                  "weekly": name.startswith("week-")}
    _dump(DATA / "digests" / f"{name}.json", payload)
    _dump(API / "digests" / f"{name}.json", payload)
    rebuild_api()
    return name


def load_recent(days: int, today: str) -> list[Digest]:
    start = Date.fromisoformat(today) - timedelta(days=days)
    out = []
    for f in sorted((DATA / "digests").glob("????-??-??.json")):
        if Date.fromisoformat(f.stem) > start:
            out.append(Digest.from_dict(json.loads(f.read_text())))
    return out


def rebuild_api() -> None:
    files = sorted((DATA / "digests").glob("*.json"), key=lambda f: (f.stem.removeprefix("week-"), f.stem), reverse=True)
    index, concepts, glossary, seen_terms = [], [], [], set()
    topics: dict[str, list[dict]] = {}
    for f in files:
        d = json.loads(f.read_text())
        name = f.stem
        index.append({
            "name": name, "date": d["date"], "weekly": name.startswith("week-"),
            "heading": d.get("heading") or pretty(d["date"]), "tldr": d.get("tldr", ""),
            "count": len(d.get("items", [])),
            "top": next((i["title"] for i in d.get("items", []) if i.get("section") == "top_story"), ""),
        })
        if not name.startswith("week-"):
            for it in d.get("items", []):
                for tag in {t.strip().lower() for t in it.get("tags", []) if t.strip()}:
                    topics.setdefault(tag, []).append({
                        "name": name, "date": d["date"], "key": it["key"], "title": it["title"],
                        "source": it["source"], "one_liner": it.get("one_liner", ""),
                        "read_minutes": it.get("read_minutes", 0), "url": it["url"],
                    })
        if (d.get("concept") or {}).get("name"):
            concepts.append(d["concept"] | {"date": d["date"], "from": name})
        for g in d.get("glossary", []):
            term = (g.get("term") or "").strip()
            if term and term.lower() not in seen_terms:
                seen_terms.add(term.lower())
                glossary.append({"term": term, "meaning": g.get("meaning", ""), "date": d["date"]})
    _dump(API / "index.json", index)
    _dump(API / "learn.json", {"concepts": concepts, "glossary": glossary})
    _dump(API / "topics.json", build_topics(topics))
    _dump(API / "config.json", {"vapidPublicKey": os.environ.get("VAPID_PUBLIC_KEY", "")})
    (DOCS / ".nojekyll").touch()


def build_topics(topics: dict[str, list[dict]]) -> dict:
    """All topics (most stories first) + 'trending': tags gaining mentions this week vs last week."""
    dates = sorted({s["date"] for stories in topics.values() for s in stories})
    trending = []
    if dates:
        end = Date.fromisoformat(dates[-1])
        week, prev = end - timedelta(days=7), end - timedelta(days=14)
        for tag, stories in topics.items():
            now = sum(1 for s in stories if Date.fromisoformat(s["date"]) > week)
            before = sum(1 for s in stories if prev < Date.fromisoformat(s["date"]) <= week)
            if now >= 2 or (now and not before):
                trending.append({"tag": tag, "this_week": now, "last_week": before})
        trending.sort(key=lambda t: (t["this_week"] - t["last_week"], t["this_week"]), reverse=True)
    all_topics = sorted(({"tag": t, "count": len(v), "stories": v[:40]} for t, v in topics.items()),
                        key=lambda t: t["count"], reverse=True)
    return {"trending": trending[:6], "topics": all_topics}

"""Sunday 'Week in review': themes of the week + the best items you might have skipped."""
from __future__ import annotations

import logging

from .llm import complete_json
from .models import Digest

log = logging.getLogger("devbrief.weekly")

PROMPT = """You wrote these daily briefings for a software engineer this week:

{items}

Write a short week-in-review as JSON:
{{"tldr": "2-3 sentences: the big themes of the week and why they matter to this reader",
  "best_ids": [up to 6 ids of the most important items, most important first],
  "concept": {{"name": "one topic worth studying this weekend, based on the week",
              "explanation": "2-3 sentences on what to learn and a concrete way to practise it",
              "interview_question": "one likely interview question on it"}}}}
Only use facts from the items above."""


def build_weekly(daily: list[Digest], cfg: dict, today: str) -> Digest:
    pool = [it for d in daily for it in d.items]
    if not pool:
        return Digest(date=today, tldr="No briefings this week.", items=[], curated_by="weekly")
    listing = "\n".join(f"[{i}] ({it.section}, score {it.score}) {it.title} — {it.one_liner}" for i, it in enumerate(pool))
    curated_by = "heuristic"
    try:
        data, curated_by = complete_json(PROMPT.format(items=listing), "You are a concise tech editor. JSON only.", cfg)
        ids = [i for i in data.get("best_ids", []) if isinstance(i, int) and 0 <= i < len(pool)]
        best = [pool[i] for i in dict.fromkeys(ids)][:6]
        tldr, concept = data.get("tldr", ""), data.get("concept") or {}
    except Exception as exc:
        log.warning("weekly LLM failed (%s) — ranking by score", exc)
        best = sorted(pool, key=lambda i: i.score, reverse=True)[:6]
        tldr, concept = "", {}
    for n, it in enumerate(best):
        it.section = "top_story" if n == 0 else "headlines"
    return Digest(date=today, tldr=tldr, items=best, concept=concept, curated_by=curated_by,
                  stats={"fetched": len(pool), "candidates": len(pool)})

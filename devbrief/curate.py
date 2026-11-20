"""Turn ~70 candidates into a tight digest: pick, explain, and teach."""
from __future__ import annotations

import logging
import re

from .filtering import HINTS
from .llm import LLMUnavailable, complete_json
from .models import Digest, Item

log = logging.getLogger("devbrief.curate")

SECTION_CAPS = {"top_story": 1, "headlines": 5, "deep_read": 2, "career": 2, "security": 2, "release_radar": 3}

SYSTEM = """You are the editor of a personal morning briefing for one software engineer.
Your job is ruthless curation: they would rather get 4 great items than 10 okay ones.
Only use facts present in the candidate title/summary — never invent numbers, names or claims.
Write in plain, direct English a busy engineer can scan on a phone. Respond with JSON only."""

PROMPT = """READER
{who}

INTERESTS (weight 1-3)
{interests}

TODAY'S CANDIDATES (id · source · kind · votes · title — summary)
{candidates}

TASK
1. Pick at most {max_items} items that this reader genuinely benefits from today. Score each 1-10
   for "how much worse off is the reader if they skip this". Drop anything below {min_score}.
   Skip: marketing fluff, minor product updates, rumours, consumer gadgets, near-duplicates
   (keep the best source for a story), funding news unless industry-shaping.
2. Put each in one section: top_story (exactly 1 — the single must-know item), headlines (news, ≤5),
   deep_read (long-form engineering/architecture posts worth 10+ min, ≤2), career (Indian/global tech
   hiring, layoffs, campus placements, salary or skills-demand trends, ≤2), security (only incidents
   or vulns a developer should act on, ≤2), release_radar (major stable releases, ≤3).
3. For each: one_liner = what happened, ≤22 words. why_read = why THIS reader should care
   (concrete: what they'll learn, what to do, how it affects their work/career), ≤25 words.
   tags = 1-3 short lowercase topic tags, reused consistently across days (e.g. "ai", "system-design",
   "security", "web", "cloud", "databases", "careers", "devtools", "open-source", "languages").
   read_minutes = honest estimate (2-25).
   takeaways = 2-3 key points, ≤16 words each, ONLY facts stated in the candidate text (fewer is fine).
   context = 1-2 sentences of background a student needs to understand the story (what the
   underlying technology/company/concept is). General knowledge, not new claims about the story.
4. tldr = one sentence capturing the day in tech for this reader.
5. concept = one technical concept that today's news makes timely and that commonly appears in
   software interviews. explanation: 2-3 simple sentences. interview_question: one likely question.
6. glossary = up to 4 jargon terms used in your picks, each explained in ≤15 words.
7. quiz = 3 multiple-choice questions testing understanding of today's picks (facts from the candidate
   text or the concepts behind them). 4 options each, exactly one correct, plausible distractors.

JSON SHAPE
{{"tldr": "...",
  "items": [{{"id": 0, "section": "headlines", "score": 8, "one_liner": "...", "why_read": "...",
             "tags": ["..."], "read_minutes": 5, "takeaways": ["..."], "context": "..."}}],
  "concept": {{"name": "...", "explanation": "...", "interview_question": "...", "related_item_id": 0}},
  "glossary": [{{"term": "...", "meaning": "..."}}],
  "quiz": [{{"question": "...", "options": ["a", "b", "c", "d"], "answer": 0, "explanation": "...", "item_id": 0}}]}}"""


def _fmt_candidates(cands: list[Item]) -> str:
    lines = []
    for idx, c in enumerate(cands):
        votes = f"{c.points}pts" if c.points else "-"
        summ = f" — {c.summary[:220]}" if c.summary else ""
        lines.append(f"[{idx}] {c.source} · {c.kind} · {votes} · {c.title}{summ}")
    return "\n".join(lines)


def _enforce(items: list[Item], max_items: int) -> list[Item]:
    """Apply section caps, exactly one top story, and the global cap."""
    items = sorted(items, key=lambda i: i.score, reverse=True)
    if items and not any(i.section == "top_story" for i in items):
        first = next((i for i in items if i.section != "release_radar"), items[0])
        first.section = "top_story"
    out, counts = [], {}
    for it in items:
        if it.section == "top_story" and counts.get("top_story"):
            it.section = "headlines"
        if counts.get(it.section, 0) >= SECTION_CAPS.get(it.section, 0):
            continue
        counts[it.section] = counts.get(it.section, 0) + 1
        out.append(it)
        if len(out) >= max_items:
            break
    return out


def curate_llm(cands: list[Item], cfg: dict, date: str) -> Digest:
    p, d = cfg["profile"], cfg["digest"]
    prompt = PROMPT.format(
        who=p["who"].strip(),
        interests="\n".join(f"- {k}: {v}" for k, v in p["interests"].items()),
        candidates=_fmt_candidates(cands),
        max_items=d["max_items"], min_score=d["min_score"],
    )
    data, provider = complete_json(prompt, SYSTEM, cfg)

    picked: list[Item] = []
    used = set()
    for row in data.get("items", []):
        try:
            idx = int(row["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= idx < len(cands) or idx in used:   # never trust an invented id
            continue
        score = float(row.get("score", 0))
        section = row.get("section", "headlines")
        if score < d["min_score"] or section not in SECTION_CAPS:
            continue
        used.add(idx)
        it = cands[idx]
        it.score, it.section = score, section
        it.one_liner = str(row.get("one_liner", "")).strip() or it.title
        it.why_read = str(row.get("why_read", "")).strip()
        it.tags = [str(t).lower() for t in row.get("tags", [])][:3]
        it.read_minutes = int(row.get("read_minutes") or 0)
        it.takeaways = [str(t).strip() for t in (row.get("takeaways") or []) if str(t).strip()][:3]
        it.context = str(row.get("context") or "").strip()
        picked.append(it)

    concept = data.get("concept") or {}
    rid = concept.pop("related_item_id", None)
    if isinstance(rid, int) and 0 <= rid < len(cands):
        concept["related_title"] = cands[rid].title
        concept["related_url"] = cands[rid].url
    return Digest(
        date=date, tldr=str(data.get("tldr", "")).strip(), items=_enforce(picked, d["max_items"]),
        concept=concept, glossary=(data.get("glossary") or [])[:4], curated_by=provider,
        quiz=_clean_quiz(data.get("quiz"), cands),
    )


def _clean_quiz(raw, cands: list[Item]) -> list[dict]:
    """Keep only well-formed questions: 4 distinct options and a valid answer index."""
    out = []
    for q in raw or []:
        try:
            opts = [str(o).strip() for o in q["options"]]
            ans = int(q["answer"])
        except (KeyError, TypeError, ValueError):
            continue
        if len(opts) != 4 or len(set(opts)) != 4 or not 0 <= ans < 4 or not str(q.get("question", "")).strip():
            continue
        iid = q.get("item_id")
        out.append({
            "question": str(q["question"]).strip(), "options": opts, "answer": ans,
            "explanation": str(q.get("explanation", "")).strip(),
            "item_key": cands[iid].key if isinstance(iid, int) and 0 <= iid < len(cands) else "",
        })
    return out[:3]


# ── Fallback: no API key or LLM failure — still send something useful ──────────

def _first_sentence(text: str, limit: int = 160) -> str:
    s = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0] if text else ""
    return s[:limit]


def _why(item: Item) -> str:
    hay = f" {item.title} {item.summary} ".lower()
    topics = [k for k, words in HINTS.items() if any(w in hay for w in words)]
    if item.points:
        return f"{item.points} upvotes on {item.source}" + (f" · relevant to {', '.join(topics[:2])}" if topics else "")
    return f"From {item.source}" + (f" · relevant to {', '.join(topics[:2])}" if topics else "")


def curate_heuristic(cands: list[Item], cfg: dict, date: str) -> Digest:
    d = cfg["digest"]
    picked = []
    for it in cands:
        if it.kind == "release":
            it.section = "release_radar"
        elif it.kind == "security":
            if it.score < 6.5:
                continue
            it.section = "security"
        elif it.kind == "blog":
            it.section = "deep_read"
        elif it.kind == "india" and any(w in f" {it.title} {it.summary} ".lower() for w in HINTS["industry"]):
            it.section = "career"
        else:
            it.section = "headlines"
        it.one_liner = _first_sentence(it.summary) or it.title
        it.why_read = _why(it)
        picked.append(it)
    return Digest(date=date, tldr="", items=_enforce(picked, d["max_items"]), curated_by="heuristic")


def curate(cands: list[Item], cfg: dict, date: str) -> Digest:
    if not cands:
        return Digest(date=date, tldr="Quiet day — nothing cleared the bar.", items=[])
    try:
        return curate_llm(cands, cfg, date)
    except LLMUnavailable as exc:
        log.warning("LLM unavailable (%s) — using heuristic curation", exc)
    except Exception as exc:
        log.exception("LLM curation failed (%s) — using heuristic curation", exc)
    return curate_heuristic(cands, cfg, date)

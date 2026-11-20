from __future__ import annotations

from datetime import date as Date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import Digest

ROOT = Path(__file__).resolve().parent.parent
SECTION_LABELS = {
    "top_story": "🔥 Must-know",
    "headlines": "📰 Headlines",
    "deep_read": "📚 Deep reads",
    "career": "💼 Careers & hiring",
    "security": "🛡️ Security watch",
    "release_radar": "🚀 Release radar",
}
_env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html", "j2"]))


def pretty(d: str) -> str:
    return Date.fromisoformat(d).strftime("%A, %d %B %Y")


def _ctx(digest: Digest, cfg: dict, heading: str | None = None) -> dict:
    order = cfg["digest"].get("sections", list(SECTION_LABELS))
    return {
        "digest": digest,
        "pretty_date": heading or pretty(digest.date),
        "sections": [(s, SECTION_LABELS[s]) for s in order if s in SECTION_LABELS],
        "total_minutes": sum(i.read_minutes or 3 for i in digest.items),
        "site_url": (cfg["delivery"].get("site_url") or "").rstrip("/"),
    }


def email_html(digest: Digest, cfg: dict, heading: str | None = None) -> str:
    return _env.get_template("email.html.j2").render(**_ctx(digest, cfg, heading))


def plain_text(digest: Digest, cfg: dict, heading: str | None = None) -> str:
    ctx = _ctx(digest, cfg, heading)
    out = [f"DevBrief — {ctx['pretty_date']}"]
    if digest.tldr:
        out += ["", f"TL;DR: {digest.tldr}"]
    for key, label in ctx["sections"]:
        items = digest.by_section(key)
        if not items:
            continue
        out += ["", label.upper()]
        for it in items:
            out += [f"• {it.title} ({it.source})", f"  {it.one_liner}"]
            if it.why_read:
                out.append(f"  Why read: {it.why_read}")
            out.append(f"  {it.url}")
    if digest.concept.get("name"):
        c = digest.concept
        out += ["", f"INTERVIEW ANGLE: {c['name']}", c.get("explanation", ""), f"Q: {c.get('interview_question', '')}"]
    return "\n".join(out)


def subject(digest: Digest, heading: str | None = None) -> str:
    day = heading or Date.fromisoformat(digest.date).strftime("%a %d %b")
    alert = "🛡️ " if digest.by_section("security") else ""
    top = digest.by_section("top_story")
    lead = top[0].title if top else (digest.tldr or "Your tech briefing")
    lead = lead if len(lead) <= 70 else lead[:67].rstrip() + "…"
    return f"☕ {alert}DevBrief · {day} — {lead}"


def push_message(digest: Digest) -> str:
    lines = []
    for sec in ("top_story", "security", "headlines", "deep_read"):
        for it in digest.by_section(sec):
            icon = {"top_story": "🔥", "security": "🛡️", "headlines": "•", "deep_read": "📚"}[sec]
            lines.append(f"{icon} {it.title}")
    if not lines:
        return "Quiet day — nothing cleared your bar."
    more = len(lines) - 5
    return "\n".join(lines[:5]) + (f"\n+{more} more" if more > 0 else "")

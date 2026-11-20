from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING = re.compile(r"^(utm_|ref$|ref_|source$|fbclid$|gclid$|mc_)", re.I)


def normalize_url(url: str) -> str:
    """Strip tracking params, fragments and trailing slashes so duplicates collapse."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if not _TRACKING.match(k)]
    path = parts.path.rstrip("/") or "/"
    host = parts.netloc.lower().removeprefix("www.")
    return urlunsplit((parts.scheme.lower() or "https", host, path, urlencode(query), ""))


@dataclass
class Item:
    title: str
    url: str
    source: str
    kind: str                       # news | blog | security | india | ai | aggregator | release
    published: datetime
    summary: str = ""
    weight: float = 1.0
    points: int = 0                 # HN points etc.
    comments_url: str = ""
    # filled in by curation
    score: float = 0.0
    section: str = ""
    one_liner: str = ""
    why_read: str = ""
    tags: list[str] = field(default_factory=list)
    read_minutes: int = 0
    takeaways: list[str] = field(default_factory=list)
    context: str = ""

    @property
    def key(self) -> str:
        return hashlib.sha1(normalize_url(self.url).encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["published"] = self.published.isoformat()
        d["key"] = self.key
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        d = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        d["published"] = datetime.fromisoformat(d["published"])
        return cls(**d)


@dataclass
class Digest:
    date: str
    tldr: str
    items: list[Item]
    concept: dict = field(default_factory=dict)    # {name, explanation, interview_question}
    glossary: list[dict] = field(default_factory=list)  # [{term, meaning}]
    quiz: list[dict] = field(default_factory=list)      # [{question, options[4], answer, explanation, item_key}]
    curated_by: str = "heuristic"
    stats: dict = field(default_factory=dict)

    def by_section(self, section: str) -> list[Item]:
        return [i for i in self.items if i.section == section]

    def to_dict(self) -> dict:
        return {
            "date": self.date, "tldr": self.tldr, "concept": self.concept,
            "glossary": self.glossary, "quiz": self.quiz, "curated_by": self.curated_by,
            "stats": self.stats, "items": [i.to_dict() for i in self.items],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Digest":
        return cls(
            date=d["date"], tldr=d.get("tldr", ""), concept=d.get("concept", {}),
            glossary=d.get("glossary", []), quiz=d.get("quiz", []), curated_by=d.get("curated_by", ""),
            stats=d.get("stats", {}), items=[Item.from_dict(i) for i in d["items"]],
        )

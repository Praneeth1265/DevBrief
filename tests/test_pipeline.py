import copy

import pytest

from devbrief import curate as curate_mod, render
from devbrief.curate import _enforce, curate
from devbrief.filtering import prefilter
from devbrief.llm import _extract_json
from devbrief.models import Item, normalize_url
from devbrief.sources import parse_feed

from fixtures import BLOG_FEED, CFG, NEWS_FEED, NOW, SECURITY_FEED, SRC, fake_llm_response


def all_items():
    return (parse_feed(NEWS_FEED, SRC["news"]) + parse_feed(BLOG_FEED, SRC["blog"])
            + parse_feed(SECURITY_FEED, SRC["security"]))


def test_parse_feed_reads_all_entries():
    items = parse_feed(NEWS_FEED, SRC["news"])
    assert len(items) == 5 and items[0].source == "Example News"


def test_normalize_url_strips_tracking():
    assert normalize_url("https://www.Example.com/a/?utm_source=x&id=2#top") == "https://example.com/a?id=2"


def test_prefilter_drops_old_blocked_duplicate_and_seen():
    items = all_items()
    seen = {next(i for i in items if "rate limiter" in i.title).key}
    cands, stats = prefilter(items, CFG, seen, NOW)
    titles = [c.title for c in cands]
    assert stats["too_old"] == 1 and stats["blocked_topic"] == 1
    assert stats["duplicate"] == 1 and stats["already_sent"] == 1
    assert not any("Black Friday" in t for t in titles)
    assert len(cands) == 3


def test_llm_curation_ignores_invented_ids_and_respects_caps(monkeypatch):
    cands, _ = prefilter(all_items(), CFG, set(), NOW)
    monkeypatch.setattr(curate_mod, "complete_json", lambda p, s, c: (fake_llm_response(cands), "gemini"))
    d = curate(cands, CFG, "2026-11-21")
    assert d.curated_by == "gemini"
    assert len(d.items) == 4                              # id 999 rejected
    assert len(d.by_section("top_story")) == 1
    assert d.concept["related_url"].startswith("https://example.com/acme")
    assert all(i.url.startswith("https://") for i in d.items)


def test_min_score_threshold(monkeypatch):
    cands, _ = prefilter(all_items(), CFG, set(), NOW)
    cfg = copy.deepcopy(CFG); cfg["digest"]["min_score"] = 8
    monkeypatch.setattr(curate_mod, "complete_json", lambda p, s, c: (fake_llm_response(cands), "gemini"))
    assert len(curate(cands, cfg, "2026-11-21").items) == 3


def test_heuristic_fallback_when_no_key(monkeypatch):
    for k in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    cands, _ = prefilter(all_items(), CFG, set(), NOW)
    d = curate(cands, CFG, "2026-11-21")
    assert d.curated_by == "heuristic" and d.items and len(d.by_section("top_story")) == 1


def test_enforce_caps_global_limit():
    items = [Item(f"t{i}", f"https://x/{i}", "s", "news", NOW, score=10 - i * 0.1, section="headlines") for i in range(10)]
    out = _enforce(items, 3)
    assert len(out) == 3 and out[0].section == "top_story"


def test_extract_json_handles_fences():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_render_escapes_html_and_builds_push(monkeypatch):
    cands, _ = prefilter(all_items(), CFG, set(), NOW)
    monkeypatch.setattr(curate_mod, "complete_json", lambda p, s, c: (fake_llm_response(cands), "gemini"))
    d = curate(cands, CFG, "2026-11-21")
    d.items[0].title = "<script>alert(1)</script>"
    html = render.email_html(d, CFG)
    assert "<script>alert" not in html and "&lt;script&gt;" in html
    assert "Interview angle" in html and "Jargon buster" in html
    assert "🛡️" in render.subject(d)
    assert render.push_message(d).startswith("🔥")


def test_api_files_for_app(monkeypatch, tmp_path):
    import json
    from devbrief import state
    monkeypatch.setattr(state, "DATA", tmp_path / "data")
    monkeypatch.setattr(state, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(state, "API", tmp_path / "docs" / "api")
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "PUBKEY")
    cands, _ = prefilter(all_items(), CFG, set(), NOW)
    monkeypatch.setattr(curate_mod, "complete_json", lambda p, s, c: (fake_llm_response(cands), "gemini"))
    state.save_digest(curate(cands, CFG, "2026-11-21"))
    api = tmp_path / "docs" / "api"
    idx = json.loads((api / "index.json").read_text())
    assert idx[0]["name"] == "2026-11-21" and idx[0]["count"] == 4 and idx[0]["top"]
    learn = json.loads((api / "learn.json").read_text())
    assert learn["concepts"][0]["name"] and len(learn["glossary"]) == 2
    assert json.loads((api / "config.json").read_text())["vapidPublicKey"] == "PUBKEY"
    item = json.loads((api / "digests" / "2026-11-21.json").read_text())["items"][0]
    assert {"key", "one_liner", "why_read", "url"} <= item.keys()


def test_vapid_keys_and_push_skip(monkeypatch):
    from devbrief import deliver
    pub, priv = deliver.generate_vapid_keys()
    assert len(pub) == 87 and len(priv) == 43
    monkeypatch.delenv("WEBPUSH_SUBSCRIPTION", raising=False)
    assert deliver.send_webpush("t", "b") is False


def test_quiz_and_topics(monkeypatch, tmp_path):
    import json
    from devbrief import state
    monkeypatch.setattr(state, "DATA", tmp_path / "data")
    monkeypatch.setattr(state, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(state, "API", tmp_path / "docs" / "api")
    cands, _ = prefilter(all_items(), CFG, set(), NOW)
    monkeypatch.setattr(curate_mod, "complete_json", lambda p, s, c: (fake_llm_response(cands), "gemini"))
    d = curate(cands, CFG, "2026-11-21")
    assert len(d.quiz) == 3                                   # malformed one dropped
    assert d.quiz[0]["item_key"] and d.quiz[2]["item_key"] == ""  # invented item id → no link
    top = d.by_section("top_story")[0]
    assert len(top.takeaways) == 3 and top.context
    state.save_digest(d)
    t = json.loads((tmp_path / "docs" / "api" / "topics.json").read_text())
    res = next(x for x in t["topics"] if x["tag"] == "resilience")
    assert res["count"] == 2 and t["trending"][0]["tag"] == "resilience"

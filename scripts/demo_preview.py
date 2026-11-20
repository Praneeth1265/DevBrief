"""Fill a local copy of the app with fictional sample data so you can try the UI offline.

    python scripts/demo_preview.py
    python -m http.server -d demo_site 8000     →  open http://localhost:8000
(Also writes demo_email.html — the optional email version.)
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from devbrief import curate as curate_mod, render, state  # noqa: E402
from devbrief.filtering import prefilter  # noqa: E402
from devbrief.sources import parse_feed  # noqa: E402
from fixtures import BLOG_FEED, CFG, NEWS_FEED, NOW, SECURITY_FEED, SRC, fake_llm_response  # noqa: E402

SITE = ROOT / "demo_site"
shutil.rmtree(SITE, ignore_errors=True)
shutil.copytree(ROOT / "docs", SITE, ignore=shutil.ignore_patterns("api"))
state.DATA, state.DOCS, state.API = SITE / "_data", SITE, SITE / "api"

items = (parse_feed(NEWS_FEED, SRC["news"]) + parse_feed(BLOG_FEED, SRC["blog"])
         + parse_feed(SECURITY_FEED, SRC["security"]))
cands, stats = prefilter(items, CFG, set(), NOW)
curate_mod.complete_json = lambda p, s, c: (fake_llm_response(cands), "gemini (sample)")
import copy  # noqa: E402
from datetime import date, timedelta  # noqa: E402
yesterday = curate_mod.curate(copy.deepcopy(cands), CFG, (date.today() - timedelta(days=1)).isoformat())
yesterday.items = yesterday.items[2:]   # a smaller previous day, so Explore has history
state.save_digest(yesterday)
digest = curate_mod.curate(cands, CFG, date.today().isoformat())
digest.stats = stats
state.save_digest(digest)
(ROOT / "demo_email.html").write_text(render.email_html(digest, CFG))
print("demo app in", SITE)

"""
Usage:
  python -m devbrief run              # fetch → curate → email + push + archive
  python -m devbrief run --dry-run    # build everything, send nothing, write preview.html
  python -m devbrief weekly           # Sunday week-in-review
  python -m devbrief test-delivery    # send a test app push / email / ntfy to check your secrets
  python -m devbrief keys             # generate VAPID keys for app notifications (run once)
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from . import deliver, render, state
from .curate import curate
from .filtering import prefilter
from .sources import fetch_all
from .weekly import build_weekly

log = logging.getLogger("devbrief")
ROOT = Path(__file__).resolve().parent.parent


def load_config(path: str | None = None) -> dict:
    return yaml.safe_load(Path(path or ROOT / "config.yaml").read_text())


def _today(cfg: dict) -> str:
    return datetime.now(ZoneInfo(cfg["digest"].get("timezone", "UTC"))).date().isoformat()


def _send(digest, cfg, page_name: str, heading: str | None, dry_run: bool) -> None:
    html = render.email_html(digest, cfg, heading)
    if dry_run:
        out = ROOT / "preview.html"
        out.write_text(html)
        print(render.subject(digest, heading))
        print(render.plain_text(digest, cfg, heading))
        log.info("dry run — wrote %s, nothing sent", out)
        return
    site = (cfg["delivery"].get("site_url") or "").rstrip("/")
    click = f"{site}/#/d/{page_name}" if site else ""
    urgent = bool(digest.by_section("security"))
    failures = 0
    if cfg["delivery"].get("app_push", True):
        try:
            title = f"☕ {heading or 'Your DevBrief is ready'}" + (" · 🛡️ security alert" if urgent else "")
            deliver.send_webpush(title, render.push_message(digest), click, urgent=urgent)
        except Exception:
            log.exception("app push failed"); failures += 1
    if cfg["delivery"].get("email"):
        try:
            deliver.send_email(render.subject(digest, heading), html, render.plain_text(digest, cfg, heading))
        except Exception:
            log.exception("email failed"); failures += 1
    if cfg["delivery"].get("push"):
        try:
            deliver.send_push(render.subject(digest, heading).removeprefix("☕ "), render.push_message(digest),
                              click, urgent=urgent)
        except Exception:
            log.exception("push failed"); failures += 1
    if failures and failures == sum(bool(cfg["delivery"].get(k)) for k in ("app_push", "email", "push")):
        sys.exit("all deliveries failed")


def cmd_run(cfg: dict, dry_run: bool) -> None:
    today = _today(cfg)
    now = datetime.now(timezone.utc)
    seen = state.load_seen()
    items = fetch_all(cfg, now)
    if not items:
        # Every source failed → that's a network/config problem, not a quiet day. Fail loudly
        # so GitHub emails you a failed-run notice instead of you getting an empty brief.
        sys.exit("no items fetched from any source")
    cands, stats = prefilter(items, cfg, set(seen), now)
    log.info("filter stats: %s", stats)
    digest = curate(cands, cfg, today)
    digest.stats = stats
    log.info("picked %d items (%s)", len(digest.items), digest.curated_by)
    if not dry_run:
        state.save_digest(digest)
        for it in digest.items:
            seen[it.key] = today
        state.save_seen(seen, today)
    _send(digest, cfg, today, None, dry_run)


def cmd_weekly(cfg: dict, dry_run: bool) -> None:
    today = _today(cfg)
    digest = build_weekly(state.load_recent(7, today), cfg, today)
    heading = f"Week in review · {render.pretty(today)}"
    if not dry_run:
        state.save_digest(digest, name=f"week-{today}", heading=heading)
    _send(digest, cfg, f"week-{today}", heading, dry_run)


def cmd_test_delivery(cfg: dict) -> None:
    site = (cfg["delivery"].get("site_url") or "").rstrip("/")
    ok_app = deliver.send_webpush("☕ DevBrief test", "✅ Notifications reach your app.", f"{site}/" if site else "")
    print(f"app push: {'ok' if ok_app else 'not configured'}")
    ok_mail = deliver.send_email("☕ DevBrief test", "<p>✅ Email delivery works.</p>", "Email delivery works.")
    ok_push = deliver.send_push("DevBrief test", "✅ Push delivery works.")
    print(f"email: {'ok' if ok_mail else 'not configured'} · push: {'ok' if ok_push else 'not configured'}")


def cmd_keys() -> None:
    pub, priv = deliver.generate_vapid_keys()
    print("Add these as GitHub secrets (Settings → Secrets → Actions):\n")
    print(f"VAPID_PUBLIC_KEY  = {pub}")
    print(f"VAPID_PRIVATE_KEY = {priv}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="devbrief")
    ap.add_argument("command", choices=["run", "weekly", "test-delivery", "keys", "rebuild-api"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    cfg = load_config(args.config)
    {"run": lambda: cmd_run(cfg, args.dry_run),
     "weekly": lambda: cmd_weekly(cfg, args.dry_run),
     "test-delivery": lambda: cmd_test_delivery(cfg),
     "keys": cmd_keys,
     "rebuild-api": state.rebuild_api}[args.command]()


if __name__ == "__main__":
    main()

"""Send the digest: Gmail (SMTP + app password) and ntfy.sh push notifications."""
from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

import requests

log = logging.getLogger("devbrief.deliver")


def send_email(subject: str, html: str, text: str) -> bool:
    sender = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    to = os.environ.get("DIGEST_TO") or sender
    if not (sender and password):
        log.warning("email skipped: GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set")
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, f"DevBrief <{sender}>", to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as s:
        s.login(sender, password.replace(" ", ""))
        s.send_message(msg)
    log.info("email sent to %s", to)
    return True


def send_push(title: str, message: str, click_url: str = "", urgent: bool = False) -> bool:
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        log.warning("push skipped: NTFY_TOPIC not set")
        return False
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    payload = {
        "topic": topic, "title": title, "message": message,
        "tags": ["coffee"], "priority": 4 if urgent else 3,
    }
    if click_url:
        payload["click"] = click_url
        payload["actions"] = [{"action": "view", "label": "Open brief", "url": click_url}]
    headers = {}
    if os.environ.get("NTFY_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['NTFY_TOKEN']}"
    r = requests.post(server, json=payload, headers=headers, timeout=20)
    r.raise_for_status()
    log.info("push sent to ntfy topic")
    return True


def _subscriptions() -> list[dict]:
    raw = (os.environ.get("WEBPUSH_SUBSCRIPTION") or "").strip()
    if not raw:
        return []
    data = json.loads(raw)
    return data if isinstance(data, list) else [data]   # one phone, or a list of devices


def send_webpush(title: str, body: str, url: str = "", urgent: bool = False, tag: str = "devbrief") -> bool:
    """Native push straight into the installed DevBrief app (Android Chrome, iOS 16.4+ home-screen app)."""
    subs = _subscriptions()
    private_key = os.environ.get("VAPID_PRIVATE_KEY")
    if not (subs and private_key):
        log.warning("app push skipped: WEBPUSH_SUBSCRIPTION / VAPID_PRIVATE_KEY not set")
        return False
    from pywebpush import WebPushException, webpush

    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag, "urgent": urgent})
    claims = {"sub": os.environ.get("VAPID_SUBJECT") or f"mailto:{os.environ.get('GMAIL_ADDRESS') or 'devbrief@example.com'}"}
    sent = 0
    for sub in subs:
        try:
            webpush(sub, payload, vapid_private_key=private_key, vapid_claims=dict(claims),
                    ttl=12 * 3600, headers={"Urgency": "high" if urgent else "normal"})
            sent += 1
        except WebPushException as exc:
            log.warning("app push to one device failed: %s", exc)
    log.info("app push sent to %d/%d device(s)", sent, len(subs))
    return sent > 0


def generate_vapid_keys() -> tuple[str, str]:
    """Return (public, private) VAPID keys, base64url — run once, store as GitHub secrets."""
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
    priv = b64(key.private_numbers().private_value.to_bytes(32, "big"))
    pub = b64(key.public_key().public_bytes(serialization.Encoding.X962,
                                            serialization.PublicFormat.UncompressedPoint))
    return pub, priv

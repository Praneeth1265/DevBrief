"""Tiny provider-agnostic LLM client (Gemini free tier or Anthropic), JSON output only."""
from __future__ import annotations

import json
import logging
import os
import re
import time

import requests

log = logging.getLogger("devbrief.llm")


class LLMUnavailable(RuntimeError):
    pass


def _extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in LLM output")
    return json.loads(text[start : end + 1])


def _post(url, headers, payload, retries=3):
    for attempt in range(retries):
        r = requests.post(url, headers=headers, json=payload, timeout=120)
        if r.status_code in (429, 500, 502, 503, 529) and attempt < retries - 1:
            time.sleep(8 * (attempt + 1))
            continue
        return r
    return r


def _gemini(prompt: str, system: str, models: list[str]) -> str:
    key = os.environ["GEMINI_API_KEY"]
    last = None
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
        }
        r = _post(url, {"x-goog-api-key": key, "Content-Type": "application/json"}, payload)
        if r.status_code == 404:          # model retired/renamed → try the next one
            log.warning("Gemini model %s not found, trying next", model)
            last = r.text
            continue
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        log.info("curated with Gemini %s", model)
        return "".join(p.get("text", "") for p in parts)
    raise LLMUnavailable(f"no Gemini model worked: {last}")


def _anthropic(prompt: str, system: str, model: str) -> str:
    r = _post(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
         "content-type": "application/json"},
        {"model": model, "max_tokens": 4096, "system": system,
         "messages": [{"role": "user", "content": prompt}]},
    )
    r.raise_for_status()
    log.info("curated with Anthropic %s", model)
    return "".join(b.get("text", "") for b in r.json()["content"])


def pick_provider(cfg: dict) -> str:
    p = cfg.get("llm", {}).get("provider", "auto")
    if p != "auto":
        return p
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "none"


def complete_json(prompt: str, system: str, cfg: dict) -> tuple[dict, str]:
    provider = pick_provider(cfg)
    llm_cfg = cfg.get("llm", {})
    if provider == "gemini":
        text = _gemini(prompt, system, llm_cfg.get("gemini_models", ["gemini-3.5-flash-lite"]))
    elif provider == "anthropic":
        text = _anthropic(prompt, system, llm_cfg.get("anthropic_model", "claude-haiku-5-5"))
    else:
        raise LLMUnavailable("no LLM API key configured")
    return _extract_json(text), provider

"""Gemini (free tier) — keyword extraction for vague titles + qualitative scoring."""
import json
import os
import time

import requests

from src.util import log

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

KEYWORD_PROMPT = """You convert social-media post titles into product search keywords.

For each input title, return the generic product type a shopper would search for on Amazon,
in 2-5 lowercase words, without brand names. If the title does not describe one physical
consumer product, return null.

Return ONLY a JSON array of strings or nulls, same length and order as the input.

Input titles:
{items}"""

ASSESS_PROMPT = """You are a product analyst for a US Shopify store that imports goods from China.
Score each product for selling to US consumers with short-video ads (TikTok, Reels, Meta).

Score fields (integers):
- problem_solving (0-15): how clearly it solves a recognizable problem or delivers a strong benefit.
- ad_potential (0-15): can the benefit be shown visually within 3 seconds, in several creative angles.
- competition_angle (0-4): realistic room to differentiate (bundle, design, positioning, audience).
- shipping_risk (0-5): 5 = small, light, durable, one-size; 0 = fragile, bulky, sized, high return risk.
- differentiation (0-5): potential to brand it or add value beyond the commodity version.

flags: list any that apply from ["battery", "electrical", "children", "food_contact", "cosmetic",
"medical_claim", "branded_or_ip", "weapon", "regulated", "seasonal", "not_a_product"].

benefit: one sentence, the customer benefit in plain words.

Return ONLY a JSON array, one object per input, same order:
{{"id": <id>, "problem_solving": n, "ad_potential": n, "competition_angle": n,
  "shipping_risk": n, "differentiation": n, "flags": [], "benefit": "..."}}

Products:
{items}"""


def _call(prompt):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    model = os.getenv("GEMINI_MODEL") or _call.model
    for attempt in range(3):
        try:
            r = requests.post(URL.format(model=model), params={"key": key}, timeout=90, json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
            })
            if r.status_code == 429:
                time.sleep(20 * (attempt + 1))
                continue
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text.strip().removeprefix("```json").removesuffix("```"))
        except Exception as e:
            log.warning("Gemini error (attempt %d): %s", attempt + 1, e)
            time.sleep(5)
    return None


_call.model = "gemini-2.5-flash"


def configure(cfg):
    _call.model = cfg.get("model", _call.model)


def extract_keywords(titles, batch=25):
    out = []
    for i in range(0, len(titles), batch):
        chunk = titles[i:i + batch]
        res = _call(KEYWORD_PROMPT.format(items="\n".join(f"- {t}" for t in chunk)))
        out += res if isinstance(res, list) and len(res) == len(chunk) else [None] * len(chunk)
    return out


def assess(cands, batch=10) -> dict:
    """Returns {key: assessment}."""
    results = {}
    for i in range(0, len(cands), batch):
        chunk = cands[i:i + batch]
        items = "\n".join(
            f'{{"id": {j}, "title": {json.dumps(c.title[:200])}, "keyword": {json.dumps(c.keyword)}}}'
            for j, c in enumerate(chunk))
        res = _call(ASSESS_PROMPT.format(items=items))
        if not isinstance(res, list):
            continue
        for obj in res:
            j = obj.get("id")
            if isinstance(j, int) and 0 <= j < len(chunk):
                results[chunk[j].key] = obj
        time.sleep(4)  # free-tier pacing
    return results

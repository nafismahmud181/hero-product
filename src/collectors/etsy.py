"""Etsy Open API v3 — active listings for seed keywords."""
import os

import requests

from src.util import Candidate, log

URL = "https://openapi.etsy.com/v3/application/listings/active"


def collect(cfg) -> list[Candidate]:
    key = os.getenv("ETSY_API_KEY")  # keystring (or "keystring:shared_secret" if Etsy asks for it)
    if not key:
        log.info("Etsy skipped: no API key")
        return []
    out = []
    for kw in cfg["seed_keywords"]:
        try:
            r = requests.get(URL, headers={"x-api-key": key}, timeout=30,
                             params={"keywords": kw, "limit": cfg["results_per_keyword"], "sort_on": "score"})
            r.raise_for_status()
            for it in r.json().get("results", []):
                p = it.get("price") or {}
                price = p["amount"] / p["divisor"] if p.get("divisor") else None
                out.append(Candidate(
                    title=it.get("title", ""), source="etsy", url=it.get("url", ""),
                    signals={"etsy_favorers": it.get("num_favorers"), "etsy_price": price, "etsy_seed": kw},
                ))
        except Exception as e:
            log.warning("Etsy '%s' error: %s", kw, e)
    log.info("Etsy: %d listings", len(out))
    return out

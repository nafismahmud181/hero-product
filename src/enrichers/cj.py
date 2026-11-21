"""CJdropshipping API — supplier price and availability."""
import os

import requests

from src.util import log, to_float

BASE = "https://developers.cjdropshipping.com/api2.0/v1"
_token = None


def _get_token():
    global _token
    if _token is None:
        r = requests.post(BASE + "/authentication/getAccessToken",
                          json={"apiKey": os.getenv("CJ_API_KEY")}, timeout=30)
        r.raise_for_status()
        _token = (r.json().get("data") or {}).get("accessToken") or ""
    return _token


def enrich(keyword) -> dict:
    if not os.getenv("CJ_API_KEY"):
        return {}
    try:
        tok = _get_token()
        if not tok:
            return {}
        r = requests.get(BASE + "/product/list", headers={"CJ-Access-Token": tok}, timeout=30,
                         params={"productNameEn": keyword, "pageSize": 10})
        r.raise_for_status()
        items = ((r.json().get("data") or {}).get("list")) or []
    except Exception as e:
        log.warning("CJ '%s' error: %s", keyword, e)
        return {}
    prices = [to_float(i.get("sellPrice")) for i in items]
    prices = [p for p in prices if p]
    return {"cj_price": min(prices) if prices else None, "cj_count": len(items)}

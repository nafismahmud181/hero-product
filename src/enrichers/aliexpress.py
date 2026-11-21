"""AliExpress Affiliate API — supplier price, order volume, rating."""
import hashlib
import hmac
import os
import time

import requests

from src.util import log, median, to_float

URL = "https://api-sg.aliexpress.com/sync"


def _sign(params, secret):
    base = "".join(f"{k}{params[k]}" for k in sorted(params))
    return hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest().upper()


def enrich(keyword) -> dict:
    key, secret = os.getenv("ALI_APP_KEY"), os.getenv("ALI_APP_SECRET")
    if not (key and secret):
        return {}
    params = {
        "app_key": key, "method": "aliexpress.affiliate.product.query",
        "sign_method": "sha256", "timestamp": str(int(time.time() * 1000)),
        "keywords": keyword, "target_currency": "USD", "target_language": "EN",
        "ship_to_country": "US", "sort": "LAST_VOLUME_DESC", "page_size": "20",
    }
    if os.getenv("ALI_TRACKING_ID"):
        params["tracking_id"] = os.getenv("ALI_TRACKING_ID")
    params["sign"] = _sign(params, secret)
    try:
        r = requests.post(URL, data=params, timeout=30)
        r.raise_for_status()
        res = (r.json().get("aliexpress_affiliate_product_query_response", {})
               .get("resp_result", {}).get("result", {}))
        prods = (res.get("products") or {}).get("product") or []
    except Exception as e:
        log.warning("AliExpress '%s' error: %s", keyword, e)
        return {}
    if not prods:
        return {}
    top = prods[:5]
    return {
        "ali_price": median([to_float(p.get("target_sale_price")) for p in top]),
        "ali_volume": sum(int(p.get("lastest_volume") or 0) for p in top),
        "ali_rating": median([to_float(p.get("evaluate_rate")) for p in top]),
        "ali_url": top[0].get("product_detail_url"),
    }

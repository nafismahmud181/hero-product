"""eBay Browse API — competitor price range and listing count (US)."""
import base64
import os

import requests

from src.util import log, median, to_float

_token = None


def _get_token():
    global _token
    if _token is None:
        cred = base64.b64encode(f"{os.getenv('EBAY_CLIENT_ID')}:{os.getenv('EBAY_CLIENT_SECRET')}".encode()).decode()
        r = requests.post("https://api.ebay.com/identity/v1/oauth2/token", timeout=30,
                          headers={"Authorization": f"Basic {cred}",
                                   "Content-Type": "application/x-www-form-urlencoded"},
                          data={"grant_type": "client_credentials",
                                "scope": "https://api.ebay.com/oauth/api_scope"})
        r.raise_for_status()
        _token = r.json()["access_token"]
    return _token


def enrich(keyword) -> dict:
    if not (os.getenv("EBAY_CLIENT_ID") and os.getenv("EBAY_CLIENT_SECRET")):
        return {}
    try:
        r = requests.get("https://api.ebay.com/buy/browse/v1/item_summary/search", timeout=30,
                         headers={"Authorization": f"Bearer {_get_token()}",
                                  "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
                         params={"q": keyword, "limit": 50, "filter": "buyingOptions:{FIXED_PRICE},conditions:{NEW}"})
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("eBay '%s' error: %s", keyword, e)
        return {}
    prices = [to_float((i.get("price") or {}).get("value")) for i in data.get("itemSummaries", [])]
    return {"ebay_listings": data.get("total", 0), "ebay_median_price": median(prices)}

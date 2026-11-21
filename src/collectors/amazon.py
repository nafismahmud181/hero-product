"""Amazon Best Sellers + Movers & Shakers (public pages, no account needed)."""
import re

from bs4 import BeautifulSoup

from src.util import Candidate, browser_session, jitter, log, to_float

BASE = "https://www.amazon.com"
LISTS = {
    "best_sellers": BASE + "/Best-Sellers/zgbs/{cat}?pg={pg}",
    "movers": BASE + "/gp/movers-and-shakers/{cat}?pg={pg}",
}


def _blocked(html: str) -> bool:
    h = html.lower()
    return "captcha" in h or "to discuss automated access" in h


def _parse(html, list_name, category):
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("[id=gridItemRoot]") or soup.select("div.zg-grid-general-faceout")
    out = []
    for it in items:
        link = it.select_one('a[href*="/dp/"]')
        if not link:
            continue
        m = re.search(r"/dp/([A-Z0-9]{10})", link.get("href", ""))
        img = it.select_one("img")
        title = (img.get("alt", "") if img else "") or link.get_text(" ", strip=True)
        if not title:
            continue
        text = it.get_text(" ", strip=True)
        rank_el = it.select_one(".zg-bdg-text")
        price_m = re.search(r"\$\s?(\d[\d,]*\.?\d*)", text)
        gain_m = re.search(r"([\d,]+)\s?%", text) if list_name == "movers" else None
        out.append(Candidate(
            title=title.strip(),
            source="amazon",
            url=f"{BASE}/dp/{m.group(1)}" if m else BASE + link["href"],
            signals={
                "amazon_asin": m.group(1) if m else None,
                "amazon_list": list_name,
                "amazon_category": category,
                "amazon_rank": int(to_float(rank_el.text)) if rank_el and to_float(rank_el.text) else None,
                "amazon_price": to_float(price_m.group(1)) if price_m else None,
                "amazon_gain_pct": to_float(gain_m.group(1)) if gain_m else None,
            },
        ))
    return out


def collect(cfg) -> list[Candidate]:
    s = browser_session()
    out = []
    lists = [k for k in LISTS if cfg.get(k, True)]
    for cat in cfg["categories"]:
        for list_name in lists:
            for pg in range(1, cfg.get("pages", 1) + 1):
                url = LISTS[list_name].format(cat=cat, pg=pg)
                try:
                    r = s.get(url, timeout=30)
                    if r.status_code != 200 or _blocked(r.text):
                        log.warning("Amazon blocked/failed (%s) %s", r.status_code, url)
                        jitter(cfg["delay_sec"])
                        continue
                    items = _parse(r.text, list_name, cat)
                    log.info("Amazon %s/%s p%d: %d items", list_name, cat, pg, len(items))
                    out += items
                except Exception as e:
                    log.warning("Amazon error %s: %s", url, e)
                jitter(cfg["delay_sec"])
    return out

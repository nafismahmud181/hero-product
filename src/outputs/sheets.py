"""Write ranked products to Google Sheets (service account)."""
import json
import os

from src.util import log

HEADER = ["Rank", "Product", "Keyword", "Decision", "Score /100", "Benefit",
          "Demand", "Profit", "Problem", "Ad potential", "Competition", "Supplier", "Ship/returns", "Differentiation",
          "Supplier $", "Landed cost $", "Sell price $", "Break-even CPA $", "Margin %",
          "Amazon rank", "Days seen", "Trend growth", "Ali orders", "eBay listings",
          "Sources", "Link", "Supplier link", "Reject reasons", "Last checked"]


def _row(i, r):
    b = json.loads(r["breakdown"])
    p, e, s, a = b["parts"], b["econ"], b["signals"], b["llm"]
    return [i, r["title"][:150], r["keyword"], r["decision"], r["total"], a.get("benefit", ""),
            p["demand"], p["profit"], p["problem_solving"], p["ad_potential"], p["competition"],
            p["supplier"], p["shipping_returns"], p["differentiation"],
            e.get("supplier_price"), e.get("landed_cost"), e.get("sell_price"), e.get("breakeven_cpa"),
            round(e["margin_pct"] * 100, 1) if e.get("margin_pct") is not None else None,
            s.get("amazon_rank"), s.get("days_seen"), s.get("trend_growth"), s.get("ali_volume"),
            s.get("ebay_listings"), r["sources"], r["url"], s.get("ali_url", ""),
            "; ".join(b["reasons"]), r["ts"][:16].replace("T", " ")]


def write(rows):
    creds, sheet_id = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"), os.getenv("GOOGLE_SHEET_ID")
    if not (creds and sheet_id):
        log.info("Sheets skipped: no credentials")
        return
    import gspread

    gc = gspread.service_account_from_dict(json.loads(creds))
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet("Ranked")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet("Ranked", rows=1000, cols=len(HEADER))
    data = [HEADER] + [[("" if v is None else v) for v in _row(i, r)] for i, r in enumerate(rows, 1)]
    ws.clear()
    ws.update(values=data, range_name="A1")
    ws.freeze(rows=1)
    log.info("Sheets: wrote %d rows", len(rows))

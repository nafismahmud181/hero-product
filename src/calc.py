"""Landed cost, contribution and break-even CPA."""
from src.util import median


def economics(s: dict, c: dict) -> dict:
    supplier = min([p for p in (s.get("ali_price"), s.get("cj_price")) if p], default=None)
    if not supplier:
        return {}
    unit = supplier * (1 - c["bulk_discount"])
    duty = unit * c["duty_rate"]
    landed = unit + c["freight_per_unit"] + duty + c["fulfillment_per_order"]

    market = median([s.get("amazon_price"), s.get("ebay_median_price")])
    price = market if market else round(unit * c["default_markup"], 2)
    payment = price * c["payment_pct"] + c["payment_fixed"]
    refunds = price * c["refund_allowance_pct"]
    be_cpa = price - landed - payment - refunds

    return {
        "supplier_price": round(supplier, 2),
        "unit_cost": round(unit, 2),
        "duty": round(duty, 2),
        "landed_cost": round(landed, 2),
        "sell_price": round(price, 2),
        "price_source": "market" if market else "markup",
        "payment_fee": round(payment, 2),
        "refund_allowance": round(refunds, 2),
        "breakeven_cpa": round(be_cpa, 2),
        "margin_pct": round(be_cpa / price, 3) if price else None,
    }

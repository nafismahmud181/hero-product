"""100-point scorecard: rule-based (demand, profit, competition, supplier) + LLM (qualitative)."""

HARD_FLAGS = {"battery", "electrical", "children", "food_contact", "cosmetic",
              "medical_claim", "branded_or_ip", "weapon", "regulated", "not_a_product"}


def _demand(s):  # max 20
    p = 0
    rank = s.get("amazon_rank")
    if rank:
        p += 6 if rank <= 20 else 4 if rank <= 50 else 2
    if (s.get("amazon_gain_pct") or 0) >= 100:
        p += 2
    if s.get("days_seen", 0) >= 5:                 # own Keepa: sustained presence
        p += 3 if s.get("rank_improving") else 2
    g = s.get("trend_growth")
    if g is not None:
        p += 5 if g > 0.2 else 3 if g > 0 else 1 if g > -0.2 else 0
        if s.get("trend_spiky"):
            p -= 2
    if (s.get("reddit_velocity") or 0) >= 30:
        p += 2
    if (s.get("etsy_favorers") or 0) >= 500:
        p += 1
    vol = s.get("ali_volume") or 0
    p += 3 if vol >= 2000 else 2 if vol >= 500 else 0
    return max(0, min(p, 20))


def _profit(e):  # max 20
    cpa = e.get("breakeven_cpa")
    if cpa is None:
        return 0
    return 20 if cpa >= 30 else 16 if cpa >= 22 else 10 if cpa >= 15 else 0


def _competition(s, a):  # max 10
    n = s.get("ebay_listings")
    p = 3 if n is None else 6 if n < 500 else 4 if n < 2000 else 2 if n < 10000 else 0
    return min(p + int(a.get("competition_angle", 0)), 10)


def _supplier(s):  # max 10
    p = 0
    r = s.get("ali_rating")
    p += 4 if r and r >= 95 else 2 if r and r >= 90 else 0
    p += 3 if (s.get("ali_volume") or 0) >= 500 else 0
    p += 3 if s.get("cj_count") else 0
    return min(p, 10)


def score(s: dict, e: dict, a: dict, cfg: dict):
    c, t = cfg["costs"], cfg["scoring"]["thresholds"]
    parts = {
        "demand": _demand(s),
        "profit": _profit(e),
        "problem_solving": min(int(a.get("problem_solving", 0)), 15),
        "ad_potential": min(int(a.get("ad_potential", 0)), 15),
        "competition": _competition(s, a),
        "supplier": _supplier(s),
        "shipping_returns": min(int(a.get("shipping_risk", 0)), 5),
        "differentiation": min(int(a.get("differentiation", 0)), 5),
    }
    total = sum(parts.values())

    reasons = []
    flags = set(a.get("flags") or []) & HARD_FLAGS
    if flags:
        reasons.append("flags: " + ", ".join(sorted(flags)))
    if e and e.get("sell_price", 0) < c["min_price"]:
        reasons.append(f"price < ${c['min_price']}")
    if e and e.get("breakeven_cpa", 0) < c["min_breakeven_cpa"]:
        reasons.append(f"break-even CPA < ${c['min_breakeven_cpa']}")
    if not e:
        reasons.append("no supplier data")

    if reasons:
        decision = "reject"
    elif total >= t["priority"]:
        decision = "priority test"
    elif total >= t["research"]:
        decision = "research more"
    elif total >= t["improve"]:
        decision = "needs improvement"
    else:
        decision = "reject"
    return total, decision, parts, reasons

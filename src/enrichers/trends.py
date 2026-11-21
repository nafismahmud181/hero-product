"""Google Trends (US, 12 months) via unofficial libraries: trendspy, fallback pytrends."""
from src.util import log


def _series(keyword):
    try:
        from trendspy import Trends
        df = Trends().interest_over_time([keyword], geo="US", timeframe="today 12-m")
    except Exception as e:
        log.debug("trendspy failed (%s), trying pytrends", e)
        from pytrends.request import TrendReq
        tr = TrendReq(hl="en-US", tz=0)
        tr.build_payload([keyword], geo="US", timeframe="today 12-m")
        df = tr.interest_over_time()
    if df is None or df.empty or keyword not in df:
        return []
    return [float(v) for v in df[keyword].tolist()]


def enrich(keyword) -> dict:
    try:
        vals = _series(keyword)
    except Exception as e:
        log.warning("Trends '%s' error: %s", keyword, e)
        return {}
    if len(vals) < 20:
        return {}
    recent, prev = vals[-13:], vals[:-13]          # last ~3 months vs previous ~9
    r_avg, p_avg = sum(recent) / len(recent), sum(prev) / len(prev)
    avg = sum(vals) / len(vals)
    return {
        "trend_avg": round(avg, 1),
        "trend_growth": round((r_avg - p_avg) / max(p_avg, 1), 2),
        "trend_spiky": max(vals) > 3 * max(avg, 1),   # one-off spike / fad warning
    }

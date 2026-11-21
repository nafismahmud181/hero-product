"""Hero product research pipeline: collect -> normalize -> enrich -> calculate -> score -> output."""
import argparse
import logging
import re

import yaml

from src import llm
from src.calc import economics
from src.collectors import amazon, etsy, reddit
from src.db import DB
from src.enrichers import aliexpress, cj, ebay, trends
from src.outputs import notify, sheets
from src.scoring import score
from src.util import jitter, log, short_keyword


# ── 1. collect ──────────────────────────────────────────────
def collect(cfg):
    cands = []
    for name, mod in (("amazon", amazon), ("reddit", reddit), ("etsy", etsy)):
        if cfg[name]["enabled"]:
            try:
                cands += mod.collect(cfg[name])
            except Exception as e:
                log.error("Collector %s failed: %s", name, e)
    log.info("Collected %d raw candidates", len(cands))
    return cands


# ── 2. normalize + dedupe ───────────────────────────────────
def normalize(cands, cfg):
    social = [c for c in cands if c.source == "reddit"]
    if social and cfg["llm"]["enabled"]:
        for c, kw in zip(social, llm.extract_keywords([c.title for c in social])):
            c.keyword = kw or ""
    for c in cands:
        if c.source != "reddit":
            c.keyword = short_keyword(c.title)

    block = re.compile(r"\b(" + "|".join(map(re.escape, cfg["blocklist"])) + r")\b", re.I)
    merged = {}
    for c in cands:
        if not c.keyword or block.search(c.title):
            continue
        if c.key in merged:
            m = merged[c.key]
            for k, v in c.signals.items():
                if v is not None and (m.signals.get(k) is None or
                                      (isinstance(v, (int, float)) and k != "amazon_rank" and v > m.signals[k])):
                    m.signals[k] = v
            if c.signals.get("amazon_rank") and (m.signals.get("amazon_rank") or 10**9) > c.signals["amazon_rank"]:
                m.signals["amazon_rank"] = c.signals["amazon_rank"]
        else:
            merged[c.key] = c
    log.info("Normalized to %d unique candidates", len(merged))
    return list(merged.values())


def priority(c):
    s = c.signals
    return ((s.get("amazon_gain_pct") or 0) / 100 + (100 - (s.get("amazon_rank") or 100)) / 20
            + (s.get("reddit_velocity") or 0) / 10 + (s.get("etsy_favorers") or 0) / 500)


# ── 3. enrich ───────────────────────────────────────────────
def enrich(c, cfg):
    e, data = cfg["enrich"], {}
    if e["trends"]:
        data.update(trends.enrich(c.keyword))
        jitter(e["trends_delay_sec"])
    for flag, mod in (("aliexpress", aliexpress), ("cj", cj), ("ebay", ebay)):
        if e[flag]:
            data.update(mod.enrich(c.keyword))
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--no-output", action="store_true", help="skip Sheets and digest")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = yaml.safe_load(open(args.config))
    run = cfg["run"]
    llm.configure(cfg["llm"])
    db = DB(run["db_path"])

    cands = normalize(collect(cfg), cfg)
    for c in cands:
        db.upsert_product(c)
        if c.signals.get("amazon_rank"):
            db.add_rank(c.key, c.signals.get("amazon_list"), c.signals.get("amazon_category"),
                        c.signals["amazon_rank"], c.signals.get("amazon_price"))
    db.c.commit()

    # choose what to enrich: cached ones are free, new ones are capped
    selected, new_budget = [], run["max_new_enrich_per_run"]
    for c in sorted(cands, key=priority, reverse=True):
        cached = db.get_enrichment(c.key, run["reenrich_after_days"])
        if cached is not None:
            c.signals.update({k: v for k, v in cached.items() if k != "llm"})
            c.llm = cached.get("llm")
            selected.append(c)
        elif new_budget > 0:
            new_budget -= 1
            data = enrich(c, cfg)
            c.signals.update(data)
            c.llm = None
            db.set_enrichment(c.key, data)
            selected.append(c)
    db.c.commit()
    log.info("Selected %d candidates for scoring", len(selected))

    # qualitative LLM assessment (only for those not cached)
    todo = [c for c in selected if not c.llm]
    if todo and cfg["llm"]["enabled"]:
        res = llm.assess(todo, cfg["llm"]["batch_size"])
        for c in todo:
            c.llm = res.get(c.key)
            if c.llm:
                cached = db.get_enrichment(c.key, run["reenrich_after_days"]) or {}
                db.set_enrichment(c.key, {**cached, "llm": c.llm})

    # calculate + score
    for c in selected:
        c.signals.update(db.rank_stats(c.key, run["history_days"]))
        econ = economics(c.signals, cfg["costs"])
        total, decision, parts, reasons = score(c.signals, econ, c.llm or {}, cfg)
        db.save_score(c.key, total, decision, {"parts": parts, "econ": econ, "signals": c.signals,
                                               "llm": c.llm or {}, "reasons": reasons})
    db.c.commit()

    rows = db.latest_scores(run["sheet_days"])
    log.info("Scored rows (last %d days): %d", run["sheet_days"], len(rows))
    if not args.no_output:
        try:
            sheets.write(rows)
        except Exception as e:
            log.error("Sheets failed: %s", e)
        notify.send(notify.build_digest(rows, run["top_n_digest"]))
    db.close()


if __name__ == "__main__":
    main()

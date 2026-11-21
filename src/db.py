import datetime as dt
import json
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS products(
  key TEXT PRIMARY KEY, title TEXT, keyword TEXT, sources TEXT, url TEXT,
  first_seen TEXT, last_seen TEXT, signals TEXT);
CREATE TABLE IF NOT EXISTS rank_history(
  key TEXT, ts TEXT, list TEXT, category TEXT, rank INTEGER, price REAL);
CREATE INDEX IF NOT EXISTS ix_rank ON rank_history(key, ts);
CREATE TABLE IF NOT EXISTS enrichment(key TEXT PRIMARY KEY, ts TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS scores(
  key TEXT, ts TEXT, total REAL, decision TEXT, breakdown TEXT);
CREATE INDEX IF NOT EXISTS ix_scores ON scores(key, ts);
"""


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _since(days) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat(timespec="seconds")


class DB:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.c = sqlite3.connect(path)
        self.c.row_factory = sqlite3.Row
        self.c.executescript(SCHEMA)

    # ── products ────────────────────────────────────────────
    def upsert_product(self, cand):
        row = self.c.execute("SELECT * FROM products WHERE key=?", (cand.key,)).fetchone()
        ts = now()
        if row:
            sources = set(row["sources"].split(",")) | {cand.source}
            signals = {**json.loads(row["signals"]), **cand.signals}
            self.c.execute("UPDATE products SET last_seen=?, sources=?, signals=? WHERE key=?",
                           (ts, ",".join(sorted(sources)), json.dumps(signals), cand.key))
        else:
            self.c.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?,?)",
                           (cand.key, cand.title, cand.keyword, cand.source, cand.url,
                            ts, ts, json.dumps(cand.signals)))

    def product(self, key):
        return self.c.execute("SELECT * FROM products WHERE key=?", (key,)).fetchone()

    # ── own rank history (Keepa replacement) ────────────────
    def add_rank(self, key, list_name, category, rank, price):
        self.c.execute("INSERT INTO rank_history VALUES (?,?,?,?,?,?)",
                       (key, now(), list_name, category, rank, price))

    def rank_stats(self, key, days):
        rows = self.c.execute(
            "SELECT ts, rank FROM rank_history WHERE key=? AND ts>=? AND rank IS NOT NULL ORDER BY ts",
            (key, _since(days))).fetchall()
        if not rows:
            return {"days_seen": 0}
        days_seen = len({r["ts"][:10] for r in rows})
        first, last = rows[0]["rank"], rows[-1]["rank"]
        return {"days_seen": days_seen, "rank_first": first, "rank_last": last,
                "rank_improving": last < first}

    # ── enrichment cache ────────────────────────────────────
    def get_enrichment(self, key, max_age_days):
        row = self.c.execute("SELECT data FROM enrichment WHERE key=? AND ts>=?",
                             (key, _since(max_age_days))).fetchone()
        return json.loads(row["data"]) if row else None

    def set_enrichment(self, key, data):
        self.c.execute("INSERT OR REPLACE INTO enrichment VALUES (?,?,?)", (key, now(), json.dumps(data)))

    # ── scores ──────────────────────────────────────────────
    def save_score(self, key, total, decision, breakdown):
        self.c.execute("INSERT INTO scores VALUES (?,?,?,?,?)",
                       (key, now(), total, decision, json.dumps(breakdown)))

    def latest_scores(self, days):
        return self.c.execute("""
            SELECT p.key, p.title, p.keyword, p.sources, p.url, s.ts, s.total, s.decision, s.breakdown
            FROM scores s JOIN products p ON p.key = s.key
            WHERE s.ts = (SELECT MAX(ts) FROM scores WHERE key = s.key) AND s.ts >= ?
            ORDER BY s.total DESC""", (_since(days),)).fetchall()

    def close(self):
        self.c.commit()
        self.c.close()

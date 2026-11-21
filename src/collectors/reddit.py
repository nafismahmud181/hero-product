"""Reddit via official API (PRAW, read-only)."""
import os
import time

from src.util import Candidate, log


def collect(cfg) -> list[Candidate]:
    cid, secret = os.getenv("REDDIT_CLIENT_ID"), os.getenv("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        log.info("Reddit skipped: no credentials")
        return []
    import praw

    reddit = praw.Reddit(client_id=cid, client_secret=secret,
                         user_agent="product-research-bot/1.0 (by u/{})".format(os.getenv("REDDIT_USERNAME", "anon")))
    out, now = [], time.time()
    for sub in cfg["subreddits"]:
        try:
            for p in reddit.subreddit(sub).top(time_filter="week", limit=cfg["posts_per_sub"]):
                age_h = max((now - p.created_utc) / 3600, 1)
                if p.stickied or p.score < cfg["min_score"] or age_h > cfg["max_age_hours"]:
                    continue
                out.append(Candidate(
                    title=p.title, source="reddit", url="https://reddit.com" + p.permalink,
                    signals={"reddit_score": p.score, "reddit_comments": p.num_comments,
                             "reddit_velocity": round(p.score / age_h, 1), "reddit_sub": sub},
                ))
        except Exception as e:
            log.warning("Reddit r/%s error: %s", sub, e)
    log.info("Reddit: %d posts", len(out))
    return out

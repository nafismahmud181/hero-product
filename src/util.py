import logging
import random
import re
import statistics
import time
from dataclasses import dataclass, field

import requests

log = logging.getLogger("research")

_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
]

_STOP = {"the", "a", "an", "for", "with", "and", "of", "to", "in", "on", "by", "new", "pack",
         "set", "pcs", "pieces", "upgraded", "premium", "best", "my", "this", "your", "is", "it"}


@dataclass
class Candidate:
    title: str
    source: str
    url: str = ""
    keyword: str = ""
    signals: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", (self.keyword or self.title).lower()).strip("-")


def browser_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(_UAS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s


def jitter(rng):
    time.sleep(random.uniform(*rng))


def short_keyword(title: str, max_words: int = 5) -> str:
    t = re.sub(r"[\(\[].*?[\)\]]", " ", title.lower())
    t = re.split(r"\s[-–|]\s|,|:", t)[0]
    words = [w for w in re.findall(r"[a-z][a-z0-9'-]*", t) if w not in _STOP]
    return " ".join(words[:max_words])


def to_float(v):
    if v is None:
        return None
    m = re.search(r"\d+(?:\.\d+)?", str(v).replace(",", ""))
    return float(m.group()) if m else None


def median(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None

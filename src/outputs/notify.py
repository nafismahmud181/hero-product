"""Top-N digest via Telegram and/or email (Gmail app password)."""
import json
import os
import smtplib
from email.mime.text import MIMEText

import requests

from src.util import log


def build_digest(rows, n):
    picks = [r for r in rows if r["decision"] != "reject"][:n]
    if not picks:
        return "Product research: no candidates passed the filters this run."
    lines = [f"Top {len(picks)} product candidates"]
    for i, r in enumerate(picks, 1):
        e = json.loads(r["breakdown"])["econ"]
        lines.append(f"\n{i}. {r['title'][:80]}\n   Score {r['total']:.0f} | {r['decision']} | "
                     f"sell ${e.get('sell_price')} | landed ${e.get('landed_cost')} | "
                     f"BE-CPA ${e.get('breakeven_cpa')}\n   {r['url']}")
    return "\n".join(lines)


def send(text):
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if tok and chat:
        try:
            for i in range(0, len(text), 4000):
                requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", timeout=30,
                              json={"chat_id": chat, "text": text[i:i + 4000],
                                    "disable_web_page_preview": True}).raise_for_status()
            log.info("Telegram digest sent")
        except Exception as e:
            log.warning("Telegram error: %s", e)

    user, pwd, to = os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"), os.getenv("DIGEST_EMAIL_TO")
    if user and pwd and to:
        try:
            msg = MIMEText(text)
            msg["Subject"], msg["From"], msg["To"] = "Product research digest", user, to
            with smtplib.SMTP_SSL(os.getenv("SMTP_HOST", "smtp.gmail.com"), 465) as s:
                s.login(user, pwd)
                s.send_message(msg)
            log.info("Email digest sent")
        except Exception as e:
            log.warning("Email error: %s", e)

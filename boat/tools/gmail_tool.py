"""Gmail tool."""
import asyncio
import email
import imaplib
import os
import re
from . import tool


def _imap():
    M = imaplib.IMAP4_SSL("imap.gmail.com")
    M.login(os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"])
    M.select("INBOX")
    return M


@tool("gmail.search", "Search Gmail (IMAP syntax).",
      {"type": "object", "properties": {
          "query": {"type": "string", "default": "UNSEEN"},
          "limit": {"type": "integer", "default": 10}}})
async def gmail_search(query="UNSEEN", limit=10):
    def _run():
        M = _imap()
        _, data = M.search(None, query)
        ids = data[0].split()[-limit:]
        out = []
        for i in ids:
            _, d = M.fetch(i, "(RFC822)")
            m = email.message_from_bytes(d[0][1])
            out.append({"from": m.get("From"),
                        "subject": m.get("Subject"),
                        "date": m.get("Date")})
        M.logout()
        return out
    return await asyncio.to_thread(_run)

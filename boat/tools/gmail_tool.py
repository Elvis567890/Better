import asyncio, email, imaplib, os, re
from . import tool

def _body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try: return part.get_payload(decode=True).decode(errors="ignore")
                except Exception: pass
        return ""
    try: return msg.get_payload(decode=True).decode(errors="ignore")
    except Exception: return ""

def _imap():
    M = imaplib.IMAP4_SSL("imap.gmail.com")
    M.login(os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"])
    M.select("INBOX"); return M

@tool("gmail.search", "Search Gmail (IMAP syntax).",
      {"type":"object","properties":{"query":{"type":"string","default":"UNSEEN"},
                                     "limit":{"type":"integer","default":10}}})
async def gmail_search(query="UNSEEN", limit=10):
    def _run():
        M = _imap()
        _, data = M.search(None, query)
        ids = data[0].split()[-limit:]
        out = []
        for i in ids:
            _, d = M.fetch(i, "(RFC822)")
            m = email.message_from_bytes(d[0][1])
            out.append({"from": m.get("From"), "subject": m.get("Subject"),
                        "date": m.get("Date"), "snippet": _body(m)[:600]})
        M.logout(); return out
    return await asyncio.to_thread(_run)

@tool("gmail.find_payments", "Scan inbox for payment confirmations.",
      {"type":"object","properties":{"since_days":{"type":"integer","default":2}}})
async def gmail_find_payments(since_days=2):
    hints = r"(paid|payment|received|deposit|mpesa|m-pesa|momo|paypal|stripe|wise|bank)"
    msgs = await gmail_search("ALL", 40)
    hits = []
    for m in msgs:
        blob = f"{m.get('subject','')} {m.get('snippet','')}".lower()
        if re.search(hints, blob):
            amounts = re.findall(r"(?:usd|ksh|kes|ugx|[$]|EUR|GBP)\s?([0-9][0-9,.]*)", blob)
            hits.append({"from": m["from"], "subject": m["subject"],
                         "amounts": amounts, "snippet": m["snippet"][:200]})
    return {"hits": hits[:20], "scanned": len(msgs)}

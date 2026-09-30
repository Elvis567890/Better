import os, httpx
from . import tool

@tool("social.telegram_post", "Post to a Telegram channel/chat.",
      {"type":"object","properties":{"chat_id":{"type":"string"}, "text":{"type":"string"}},
       "required":["chat_id","text"]})
async def social_telegram_post(chat_id, text):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
        return {"ok": r.status_code == 200, "body": r.text[:400]}

@tool("social.whatsapp_send", "Send WhatsApp via Twilio.",
      {"type":"object","properties":{"to":{"type":"string"}, "body":{"type":"string"}},
       "required":["to","body"]})
async def social_whatsapp_send(to, body):
    sid = os.environ["TWILIO_SID"]; tok = os.environ["TWILIO_TOKEN"]; frm = os.environ["TWILIO_WA_FROM"]
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                         auth=(sid, tok),
                         data={"From": f"whatsapp:{frm}", "To": f"whatsapp:{to}", "Body": body})
        return {"ok": r.status_code in (200,201), "body": r.text[:400]}

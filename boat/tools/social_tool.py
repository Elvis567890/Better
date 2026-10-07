"""Social tool."""
import os
import httpx
from . import tool


@tool("social.whatsapp_send", "Send WhatsApp via Twilio.",
      {"type": "object", "properties": {
          "to": {"type": "string"}, "body": {"type": "string"}},
       "required": ["to", "body"]})
async def social_whatsapp_send(to, body):
    sid = os.environ["TWILIO_SID"]
    tok = os.environ["TWILIO_TOKEN"]
    frm = os.environ["TWILIO_WA_FROM"]
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=(sid, tok),
            data={"From": f"whatsapp:{frm}",
                  "To": f"whatsapp:{to}", "Body": body})
        return {"ok": r.status_code in (200, 201), "body": r.text[:400]}

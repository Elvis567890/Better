import os, httpx
from . import tool

@tool("telegram.send", "Send a Telegram message.",
      {"type":"object","properties":{"chat_id":{"type":"string"}, "text":{"type":"string"}},
       "required":["chat_id","text"]})
async def telegram_send(chat_id, text):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": chat_id, "text": text[:4000]})
        return {"ok": r.status_code == 200, "body": r.text[:300]}

@tool("telegram.send_document", "Send a file to Telegram.",
      {"type":"object","properties":{"chat_id":{"type":"string"}, "path":{"type":"string"},
                                     "caption":{"type":"string","default":""}},
       "required":["chat_id","path"]})
async def telegram_send_document(chat_id, path, caption=""):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    async with httpx.AsyncClient(timeout=120) as c:
        with open(path, "rb") as f:
            r = await c.post(f"https://api.telegram.org/bot{token}/sendDocument",
                             data={"chat_id": chat_id, "caption": caption},
                             files={"document": f})
        return {"ok": r.status_code == 200, "body": r.text[:300]}

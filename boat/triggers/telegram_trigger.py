import asyncio, logging, os
import httpx
from ..brain import Boat

log = logging.getLogger("boat.telegram")

class TelegramTrigger:
    def __init__(self, boat, token=None, allowed=None):
        self.boat = boat
        self.token = token or os.environ["TELEGRAM_BOT_TOKEN"]
        self.allowed = allowed or set(filter(None, os.environ.get("TELEGRAM_ALLOWED", "").split(",")))
        self.offset = 0

    async def _get_updates(self):
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        async with httpx.AsyncClient(timeout=45) as c:
            r = await c.get(url, params={"timeout": 30, "offset": self.offset})
            return r.json().get("result", [])

    async def run(self):
        log.info("Telegram trigger up")
        while True:
            try:
                for u in await self._get_updates():
                    self.offset = u["update_id"] + 1
                    msg = u.get("message") or u.get("channel_post") or {}
                    text = (msg.get("text") or "").strip()
                    chat_id = str((msg.get("chat") or {}).get("id") or "")
                    if not text or not chat_id: continue
                    if self.allowed and chat_id not in self.allowed: continue
                    if not text.lower().startswith("boat"): continue
                    cmd = text.split(",", 1)[1].strip() if "," in text else text[4:].strip()
                    cmd = cmd or "make money anywhere today"
                    asyncio.create_task(self.boat.handle(cmd, source="telegram", reply_to=chat_id))
            except Exception as e:
                log.exception("telegram poll error: %s", e)
                await asyncio.sleep(3)

"""Ask tool."""
import time
from . import tool


@tool("telegram.ask", "Ask the user a question on Telegram.",
      {"type": "object", "properties": {
          "chat_id": {"type": "string"},
          "question": {"type": "string"},
          "mission_id": {"type": "string"}},
       "required": ["chat_id", "question"]})
async def ask(chat_id, question, mission_id="", **_i):
    from .telegram_tool import telegram_send
    r = await telegram_send(chat_id=str(chat_id), text=f"❓ {question}")
    return {"ok": r.get("ok", False), "awaiting_input": True,
            "mission_id": mission_id, "asked_at": time.time()}

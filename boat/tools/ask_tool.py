"""Ask the user a question mid-mission and mark it as awaiting input."""
import time
from . import tool


@tool(
    "telegram.ask",
    "Ask the user a question on Telegram. Use this when a human decision is required "
    "(payment destination, scope confirmation, KYC, etc.).",
    {"type": "object", "properties": {
        "chat_id": {"type": "string"},
        "question": {"type": "string"},
        "mission_id": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}},
    }, "required": ["chat_id", "question"]},
)
async def ask(chat_id, question, mission_id="", options=None):
    from .telegram_tool import telegram_send
    text = f"❓ {question}"
    if options:
        text += "\n\nReply with one of:\n" + "\n".join(f"  • {o}" for o in options)
    r = await telegram_send(chat_id=str(chat_id), text=text)
    return {"ok": r.get("ok", False),
            "awaiting_input": True,
            "mission_id": mission_id,
            "asked_at": time.time()}

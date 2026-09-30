import asyncio, os
from fastapi import FastAPI, Form
from ..brain import Boat

app = FastAPI()
boat = Boat()

@app.post("/whatsapp")
async def whatsapp(From: str = Form(...), Body: str = Form(...)):
    text = (Body or "").strip()
    if text.lower().startswith("boat"):
        cmd = text.split(",", 1)[1].strip() if "," in text else text[4:].strip()
        asyncio.create_task(boat.handle(cmd or "make money anywhere today",
                                        source="whatsapp", reply_to=From))
    return {"ok": True}

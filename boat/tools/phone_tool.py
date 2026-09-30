import asyncio
from . import tool

async def _adb(*args):
    p = await asyncio.create_subprocess_exec("adb", *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await p.communicate()
    return out.decode(errors="ignore"), err.decode(errors="ignore")

@tool("phone.contacts", "List phone contacts via adb.", {"type":"object","properties":{}})
async def phone_contacts():
    out, err = await _adb("shell", "content", "query",
                          "--uri", "content://com.android.contacts/data/phones",
                          "--projection", "display_name:data1")
    rows = []
    for line in out.splitlines():
        if "display_name=" in line:
            row = {p.split("=",1)[0].strip(): p.split("=",1)[1].strip()
                   for p in line.split(",") if "=" in p}
            rows.append(row)
    return {"count": len(rows), "contacts": rows[:200], "stderr": err[:500]}

@tool("phone.gallery", "Recent phone gallery photos.", {"type":"object","properties":{"limit":{"type":"integer","default":20}}})
async def phone_gallery(limit=20):
    out, _ = await _adb("shell", "ls", "-t", "/sdcard/DCIM/Camera")
    return {"files": [f for f in out.split() if f.lower().endswith((".jpg",".png",".mp4"))][:limit]}

@tool("phone.sms", "Dump last N SMS messages.", {"type":"object","properties":{"limit":{"type":"integer","default":30}}})
async def phone_sms(limit=30):
    out, err = await _adb("shell", "content", "query", "--uri", "content://sms/inbox",
                          "--projection", "address:body:date")
    msgs = [dict(p.split("=",1) for p in line.split(",") if "=" in p)
            for line in out.splitlines() if "body=" in line]
    return {"count": len(msgs), "messages": msgs[-limit:], "stderr": err[:300]}

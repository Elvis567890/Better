"""Phone tool (adb)."""
import asyncio
from . import tool


async def _adb(*args):
    p = await asyncio.create_subprocess_exec(
        "adb", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    out, err = await p.communicate()
    return out.decode(errors="ignore"), err.decode(errors="ignore")


@tool("phone.sms", "Dump last N SMS messages.",
      {"type": "object", "properties": {
          "limit": {"type": "integer", "default": 30}}})
async def phone_sms(limit=30):
    out, err = await _adb("shell", "content", "query",
                          "--uri", "content://sms/inbox",
                          "--projection", "address:body:date")
    msgs = [dict(p.split("=", 1) for p in line.split(",") if "=" in p)
            for line in out.splitlines() if "body=" in line]
    return {"count": len(msgs), "messages": msgs[-limit:]}

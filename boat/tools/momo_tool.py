"""MoMo tool."""
import os
import httpx
from . import tool


@tool("momo.recent", "List recent MoMo transactions.",
      {"type": "object", "properties": {
          "limit": {"type": "integer", "default": 20}}})
async def momo_recent(limit=20):
    base = os.environ.get("MOMO_BASE_URL")
    sub = os.environ.get("MOMO_SUBSCRIPTION_KEY")
    if not (base and sub):
        return {"ok": False, "reason": "MOMO_* secrets not set"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{base}/collection/v1_0/account/balance",
                        headers={"Ocp-Apim-Subscription-Key": sub})
        return {"ok": r.status_code == 200, "body": r.text[:2000]}

import os, time, httpx
from . import tool

@tool("momo.recent", "List recent MoMo/M-Pesa transactions.",
      {"type":"object","properties":{"limit":{"type":"integer","default":20}}})
async def momo_recent(limit=20):
    base = os.environ.get("MOMO_BASE_URL"); sub = os.environ.get("MOMO_SUBSCRIPTION_KEY")
    if not (base and sub):
        return {"ok": False, "reason": "MOMO_BASE_URL / MOMO_SUBSCRIPTION_KEY not set"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{base}/collection/v1_0/account/balance",
                        headers={"Ocp-Apim-Subscription-Key": sub})
        return {"ok": r.status_code == 200, "status": r.status_code, "body": r.text[:2000]}

@tool("momo.verify", "Verify a payment reference.",
      {"type":"object","properties":{"ref":{"type":"string"},
                                     "amount":{"type":"number"},
                                     "currency":{"type":"string","default":"UGX"}},
       "required":["ref"]})
async def momo_verify(ref, amount=None, currency="UGX"):
    base = os.environ.get("MOMO_BASE_URL"); sub = os.environ.get("MOMO_SUBSCRIPTION_KEY")
    if not (base and sub): return {"ok": False, "reason": "momo not configured", "ref": ref}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{base}/collection/v1_0/requesttopay/{ref}",
                        headers={"Ocp-Apim-Subscription-Key": sub})
        return {"ok": r.status_code == 200, "ref": ref, "body": r.text[:2000], "ts": time.time()}

"""Create throwaway emails and sign up to whitelisted services."""
import json, os, random, re, string
import httpx
from . import tool

MAILTM = "https://api.mail.tm"


def _rand(n=10):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


@tool(
    "accounts.new_email",
    "Create a throwaway email address via mail.tm. Returns address + password.",
    {"type": "object", "properties": {
        "local_part": {"type": "string", "description": "optional prefix, e.g. 'boat'"},
    }},
)
async def new_email(local_part=None):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{MAILTM}/domains")
        r.raise_for_status()
        domains = [d["domain"] for d in r.json()["hydra:member"] if d.get("isActive")]
        if not domains:
            return {"ok": False, "error": "no active mail.tm domains"}
        domain = domains[0]
        address = f"{(local_part or 'boat')}_{_rand(8)}@{domain}"
        password = _rand(16)

        r = await c.post(f"{MAILTM}/accounts",
                         json={"address": address, "password": password})
        if r.status_code not in (200, 201):
            return {"ok": False, "status": r.status_code, "body": r.text[:400]}

        return {"ok": True, "address": address, "password": password,
                "note": "Use accounts.read_email to fetch verification links."}


@tool(
    "accounts.read_email",
    "Read messages for a mail.tm account and return subjects + links.",
    {"type": "object", "properties": {
        "address": {"type": "string"},
        "password": {"type": "string"},
    }, "required": ["address", "password"]},
)
async def read_email(address, password):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{MAILTM}/token",
                         json={"address": address, "password": password})
        token = r.json().get("token")
        if not token:
            return {"ok": False, "error": "login failed"}
        r = await c.get(f"{MAILTM}/messages",
                        headers={"Authorization": f"Bearer {token}"})
        msgs = r.json().get("hydra:member", [])[:10]
        out = []
        for m in msgs:
            r2 = await c.get(f"{MAILTM}/messages/{m['id']}",
                             headers={"Authorization": f"Bearer {token}"})
            j = r2.json()
            body = j.get("text") or ""
            if not body and isinstance(j.get("html"), list) and j["html"]:
                body = j["html"][0]
            links = re.findall(r"https?://[^\s\"'<>]+", body or "")
            out.append({
                "from": m.get("from", {}).get("address"),
                "subject": m.get("subject"),
                "links": links[:8],
            })
        return {"ok": True, "count": len(out), "messages": out}


WHITELIST = ["reddit.com", "github.com", "gumroad.com", "substack.com",
             "dev.to", "medium.com", "hashnode.com", "bearblog.dev"]

BLOCKED = {
    "tiktok.com": "TikTok aggressively bans automation.",
    "instagram.com": "Instagram bans automation.",
    "facebook.com": "Facebook bans automation.",
    "twitter.com": "Twitter/X requires phone verify.",
    "x.com": "Twitter/X requires phone verify.",
    "upwork.com": "Upwork requires KYC.",
    "fiverr.com": "Fiverr requires KYC.",
    "paypal.com": "PayPal requires KYC + phone.",
    "stripe.com": "Stripe requires KYC.",
    "shopify.com": "Shopify requires KYC + phone.",
}


@tool(
    "accounts.can_register",
    "Check whether BOAT is allowed to auto-register on a given service. "
    "Returns allow/block with the reason.",
    {"type": "object", "properties": {
        "service_url": {"type": "string"},
    }, "required": ["service_url"]},
)
async def can_register(service_url):
    from urllib.parse import urlparse
    host = urlparse(service_url).netloc.lower().lstrip("www.")
    for b, why in BLOCKED.items():
        if b in host:
            return {"ok": False, "allowed": False, "action": "ask_human",
                    "reason": why, "host": host}
    if any(w in host for w in WHITELIST):
        return {"ok": True, "allowed": True, "host": host}
    return {"ok": False, "allowed": False, "action": "ask_human",
            "reason": f"{host} is not on the automation whitelist.", "host": host}

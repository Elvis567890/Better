"""Accounts vault. Store and retrieve credentials the owner has provided.

You register accounts once. BOAT uses them forever after.
Every account lives in boat.db (vault table) and is available via
vault.get, so tools can act as you.

Rules:
- vault.save_account   store credentials
- vault.get_account    retrieve by service name
- vault.list_accounts  show what's stored (names only, not secrets)
- vault.mark_used      update last_used

Credentials never appear in Telegram messages or logs.
"""
import json
import os
import time

from . import tool


def _db():
    from .memory import Memory
    m = Memory()
    m.db.executescript("""
    CREATE TABLE IF NOT EXISTS vault(
      service TEXT PRIMARY KEY,
      kind TEXT,
      username TEXT,
      password TEXT,
      extra TEXT,
      notes TEXT,
      created REAL,
      last_used REAL
    );
    """)
    m.db.commit()
    return m


@tool(
    "vault.save_account",
    "Store an account the owner has provided. Use once per service. "
    "kind examples: 'email', 'paypal', 'momo', 'gmail', 'upwork', "
    "'twitter', 'github', 'generic'.",
    {"type": "object", "properties": {
        "service": {"type": "string",
                    "description": "short name, e.g. 'paypal_personal'"},
        "kind": {"type": "string",
                 "description": "category, e.g. 'paypal' or 'email'"},
        "username": {"type": "string",
                     "description": "login email or username"},
        "password": {"type": "string",
                     "description": "password or API key"},
        "extra": {"type": "object",
                  "description": "any additional fields (api_key, phone, "
                                 "recovery_email, etc.)"},
        "notes": {"type": "string"},
    }, "required": ["service"]},
    danger="high",
)
async def save_account(service, kind="generic", username="",
                       password="", extra=None, notes="", **_i):
    m = _db()
    now = time.time()
    m.db.execute(
        "INSERT OR REPLACE INTO vault(service,kind,username,password,"
        "extra,notes,created,last_used) "
        "VALUES(?,?,?,?,?,?,COALESCE((SELECT created FROM vault "
        "WHERE service=?),?),?)",
        (service, kind, username, password,
         json.dumps(extra or {}), notes, service, now, now))
    m.db.commit()
    return {"ok": True, "service": service, "kind": kind}


@tool(
    "vault.get_account",
    "Retrieve stored credentials for a service. Returns username, password, "
    "and any extra fields. Used by tools that act on behalf of the owner.",
    {"type": "object", "properties": {
        "service": {"type": "string"},
    }, "required": ["service"]},
    danger="high",
)
async def get_account(service, **_i):
    m = _db()
    row = m.db.execute(
        "SELECT kind,username,password,extra,notes FROM vault "
        "WHERE service=?", (service,)).fetchone()
    if not row:
        # try a fuzzy match: any service whose name contains the query
        row = m.db.execute(
            "SELECT kind,username,password,extra,notes,service FROM vault "
            "WHERE service LIKE ? ORDER BY last_used DESC LIMIT 1",
            (f"%{service}%",)).fetchone()
        if not row:
            return {"ok": False, "reason": f"no account for '{service}'"}
        m.db.execute("UPDATE vault SET last_used=? WHERE service=?",
                     (time.time(), row[5]))
    else:
        m.db.execute("UPDATE vault SET last_used=? WHERE service=?",
                     (time.time(), service))
    m.db.commit()

    kind, username, password, extra, notes = row[0], row[1], row[2], row[3], row[4]
    try:
        extra_obj = json.loads(extra or "{}")
    except Exception:
        extra_obj = {}
    return {
        "ok": True,
        "service": service,
        "kind": kind,
        "username": username,
        "password": password,
        "extra": extra_obj,
        "notes": notes,
    }


@tool(
    "vault.list_accounts",
    "List the names of stored accounts (no passwords). Use to see what "
    "the owner has provided.",
    {"type": "object", "properties": {}},
    danger="low",
)
async def list_accounts(**_i):
    m = _db()
    rows = m.db.execute(
        "SELECT service,kind,username,last_used FROM vault "
        "ORDER BY last_used DESC").fetchall()
    return {
        "ok": True,
        "count": len(rows),
        "accounts": [
            {"service": r[0], "kind": r[1],
             "username": r[2], "last_used": r[3]}
            for r in rows
        ],
    }


@tool(
    "vault.forget",
    "Remove a stored account.",
    {"type": "object", "properties": {"service": {"type": "string"}},
     "required": ["service"]},
    danger="high",
)
async def forget(service, **_i):
    m = _db()
    m.db.execute("DELETE FROM vault WHERE service=?", (service,))
    m.db.commit()
    return {"ok": True, "service": service, "removed": True}


# ==================================================================
# Act on behalf of a stored account
# ==================================================================
@tool(
    "account.ask_owner",
    "Ask the owner to provide credentials for a service. Sends a message "
    "on Telegram explaining exactly what to send back.",
    {"type": "object", "properties": {
        "service": {"type": "string"},
        "kind": {"type": "string"},
        "why": {"type": "string"},
    }, "required": ["service"]},
    danger="low",
)
async def ask_owner(service, kind="generic", why="", **_i):
    chat = os.environ.get("TELEGRAM_ALLOWED", "").split(",")[0].strip()
    if not chat:
        return {"ok": False, "reason": "no TELEGRAM_ALLOWED"}
    text = (
        f"🔐 I need credentials for **{service}** to continue.\n\n"
        f"Kind: {kind}\n"
        f"Reason: {why or 'to complete the task'}\n\n"
        f"Reply with this format:\n"
        f"  service: {service}\n"
        f"  kind: {kind}\n"
        f"  username: <your login email>\n"
        f"  password: <your password>\n"
        f"  extra: key1=value1; key2=value2\n\n"
        f"Once you send that, I'll store it in the vault and continue."
    )
    from .telegram_tool import telegram_send
    r = await telegram_send(chat_id=chat, text=text)
    return {"ok": r.get("ok"), "asked_for": service}


@tool(
    "account.parse_owner_reply",
    "Parse a message the owner sent back with credentials, and store it "
    "in the vault. Use this when the reply has the service:/username:/"
    "password: format.",
    {"type": "object", "properties": {
        "text": {"type": "string"},
    }, "required": ["text"]},
    danger="high",
)
async def parse_owner_reply(text, **_i):
    fields = {}
    for line in (text or "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip().lower()] = v.strip()
    if not fields.get("service"):
        return {"ok": False, "reason": "no 'service:' field"}

    extra = {}
    if fields.get("extra"):
        for pair in fields["extra"].split(";"):
            if "=" in pair:
                a, b = pair.split("=", 1)
                extra[a.strip()] = b.strip()

    return await save_account(
        service=fields["service"],
        kind=fields.get("kind", "generic"),
        username=fields.get("username", ""),
        password=fields.get("password", ""),
        extra=extra,
                         )

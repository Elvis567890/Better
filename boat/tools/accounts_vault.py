"""Accounts vault."""
import json
import time
from . import tool


@tool("vault.save_account", "Store credentials for a service.",
      {"type": "object", "properties": {
          "service": {"type": "string"}, "kind": {"type": "string"},
          "username": {"type": "string"}, "password": {"type": "string"},
          "extra": {"type": "object"}, "notes": {"type": "string"}},
       "required": ["service"]}, danger="high")
async def save_account(service, kind="generic", username="",
                       password="", extra=None, notes="", **_i):
    from ..memory import Memory
    m = Memory()
    now = time.time()
    m.db.execute(
        "INSERT OR REPLACE INTO vault(service,kind,username,password,"
        "extra,notes,created,last_used) "
        "VALUES(?,?,?,?,?,?,COALESCE((SELECT created FROM vault WHERE service=?),?),?)",
        (service, kind, username, password, json.dumps(extra or {}),
         notes, service, now, now))
    m.db.commit()
    return {"ok": True, "service": service}


@tool("vault.get_account", "Retrieve stored credentials.",
      {"type": "object", "properties": {"service": {"type": "string"}},
       "required": ["service"]}, danger="high")
async def get_account(service, **_i):
    from ..memory import Memory
    m = Memory()
    row = m.db.execute(
        "SELECT kind,username,password,extra,notes FROM vault "
        "WHERE service=?", (service,)).fetchone()
    if not row:
        return {"ok": False, "reason": f"no account for {service}"}
    m.db.execute("UPDATE vault SET last_used=? WHERE service=?",
                 (time.time(), service))
    m.db.commit()
    try:
        extra_obj = json.loads(row[3] or "{}")
    except Exception:
        extra_obj = {}
    return {"ok": True, "service": service, "kind": row[0],
            "username": row[1], "password": row[2],
            "extra": extra_obj, "notes": row[4]}

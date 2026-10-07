"""Payment tracking."""
import os
import time
from . import tool


@tool("payments.owner_confirm", "Owner confirms a payment.",
      {"type": "object", "properties": {"client": {"type": "string"}},
       "required": ["client"]})
async def owner_confirm(client, **_i):
    from ..memory import Memory
    m = Memory()
    m.db.execute("""CREATE TABLE IF NOT EXISTS pending_payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client TEXT, amount REAL, currency TEXT, ref TEXT,
        raw TEXT, mission_id TEXT, status TEXT, created REAL)""")
    row = m.db.execute(
        "SELECT id, amount, currency, ref, mission_id FROM pending_payments "
        "WHERE client=? AND status='awaiting_owner' "
        "ORDER BY created DESC LIMIT 1", (client,)).fetchone()
    if not row:
        return {"ok": False, "reason": f"no pending payment for {client}"}
    pid, amount, currency, ref, mission = row
    m.db.execute("UPDATE pending_payments SET status='confirmed' WHERE id=?", (pid,))
    m.record_payment(mission or "", "customer_verified", amount, currency,
                     ref=ref or "", verified=1)
    m.db.commit()
    return {"ok": True, "client": client, "amount": amount}


@tool("payments.owner_reject", "Owner rejects a payment.",
      {"type": "object", "properties": {"client": {"type": "string"}},
       "required": ["client"]})
async def owner_reject(client, **_i):
    from ..memory import Memory
    m = Memory()
    m.db.execute("""CREATE TABLE IF NOT EXISTS pending_payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client TEXT, amount REAL, currency TEXT, ref TEXT,
        raw TEXT, mission_id TEXT, status TEXT, created REAL)""")
    m.db.execute("UPDATE pending_payments SET status='rejected' "
                 "WHERE client=? AND status='awaiting_owner'", (client,))
    m.db.commit()
    return {"ok": True, "client": client, "note": "will be chased"}

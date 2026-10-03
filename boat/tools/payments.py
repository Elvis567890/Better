"""Customer-verified payments.

Instead of reading the phone's SMS, BOAT asks the customer for proof,
records it, and pings the owner to confirm. Owner confirmation is the
strongest signal but takes 10 seconds.
"""
import os, re, time
from . import tool

# Where the client should pay
MOMO_NUMBER = os.environ.get("PAY_MOMO", "")
MOMO_NAME = os.environ.get("PAY_MOMO_NAME", "")
PAYPAL_EMAIL = os.environ.get("PAY_PAYPAL", "")
OWNER_CHAT = os.environ.get("TELEGRAM_ALLOWED", "")


def _pay_lines():
    lines = []
    if MOMO_NUMBER:
        lines.append(f"• MTN MoMo: {MOMO_NUMBER}" + (f" ({MOMO_NAME})" if MOMO_NAME else ""))
    if PAYPAL_EMAIL:
        lines.append(f"• PayPal: {PAYPAL_EMAIL}")
    return "\n".join(lines) or "• (no payout method configured — set PAY_MOMO or PAY_PAYPAL)"


@tool(
    "payments.ask_customer",
    "Send a client the payment instructions and the required proof format. "
    "Call this when work is delivered and money is due.",
    {"type": "object", "properties": {
        "channel": {"type": "string", "enum": ["email", "telegram", "whatsapp"]},
        "to":     {"type": "string", "description": "email address or chat id"},
        "amount": {"type": "number"},
        "currency": {"type": "string", "default": "UGX"},
        "note":   {"type": "string", "description": "short note about what this pays for"},
    }, "required": ["channel", "to", "amount"]},
)
async def ask_customer(channel, to, amount, currency="UGX", note=""):
    msg = (
        f"Hi! Payment for {note or 'the work'}: {amount:,.0f} {currency}.\n\n"
        f"Pay here:\n{_pay_lines()}\n\n"
        f"When done, please reply with ONE of:\n"
        f"  1. The confirmation SMS you received from MTN\n"
        f"  2. A screenshot of the confirmation\n"
        f"  3. The transaction reference number\n\n"
        f"Thanks!"
    )
    if channel == "telegram":
        from .telegram_tool import telegram_send
        r = await telegram_send(chat_id=to, text=msg)
    elif channel == "whatsapp":
        from .social_tool import social_whatsapp_send
        r = await social_whatsapp_send(to=to, body=msg)
    else:
        r = {"ok": False, "error": "email sending not wired here; use gmail tool"}
    return {"ok": r.get("ok", False), "sent_to": to, "amount": amount,
            "currency": currency}


@tool(
    "payments.record_proof",
    "Record the proof a customer sent. Params: client, amount, currency, "
    "transaction_ref OR raw_text (the SMS/screenshot text they sent). "
    "Notifies the owner to confirm. Does NOT mark as paid until owner confirms.",
    {"type": "object", "properties": {
        "client":   {"type": "string"},
        "amount":   {"type": "number"},
        "currency": {"type": "string", "default": "UGX"},
        "transaction_ref": {"type": "string"},
        "raw_text": {"type": "string"},
        "mission_id": {"type": "string"},
    }, "required": ["client", "amount"]},
)
async def record_proof(client, amount, currency="UGX",
                       transaction_ref="", raw_text="", mission_id=""):
    from ..memory import Memory
    m = Memory()
    # extract ref from raw text if not given
    if not transaction_ref and raw_text:
        m_ = re.search(r"(?:ref|code|id)[:\s]+([A-Z0-9\.\-]{6,})",
                       raw_text, re.IGNORECASE)
        transaction_ref = m_.group(1) if m_ else ""

    m.db.execute(
        """CREATE TABLE IF NOT EXISTS pending_payments(
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           client TEXT, amount REAL, currency TEXT, ref TEXT,
           raw TEXT, mission_id TEXT, status TEXT, created REAL)""")
    m.db.execute(
        """INSERT INTO pending_payments
           (client, amount, currency, ref, raw, mission_id, status, created)
           VALUES (?,?,?,?,?,?,?,?)""",
        (client, amount, currency, transaction_ref, raw_text[:1000],
         mission_id, "awaiting_owner", time.time()))
    m.db.commit()

    # ping the owner
    if OWNER_CHAT:
        from .telegram_tool import telegram_send
        await telegram_send(
            chat_id=OWNER_CHAT,
            text=(f"💰 {client} says they paid {amount:,.0f} {currency}\n"
                  f"Ref: {transaction_ref or '(none given)'}\n\n"
                  f"Reply:\n"
                  f"  yes {client}   → mark paid\n"
                  f"  no  {client}   → mark unpaid / chase"))
    return {"ok": True, "client": client, "amount": amount,
            "ref": transaction_ref, "status": "awaiting_owner"}


@tool(
    "payments.owner_confirm",
    "Owner confirms a payment is real. This is the ONLY step that "
    "marks money as received in boat.db.",
    {"type": "object", "properties": {
        "client": {"type": "string"},
    }, "required": ["client"]},
)
async def owner_confirm(client):
    from ..memory import Memory
    m = Memory()
    row = m.db.execute(
        """SELECT id, amount, currency, ref, mission_id
           FROM pending_payments
           WHERE client=? AND status='awaiting_owner'
           ORDER BY created DESC LIMIT 1""", (client,)).fetchone()
    if not row:
        return {"ok": False, "reason": f"no pending payment for {client}"}
    pid, amount, currency, ref, mission = row
    m.db.execute("UPDATE pending_payments SET status='confirmed' WHERE id=?", (pid,))
    m.record_payment(mission or "", "customer_verified", amount, currency,
                     ref=ref or "", verified=1)
    m.db.commit()
    if OWNER_CHAT:
        from .telegram_tool import telegram_send
        await telegram_send(chat_id=OWNER_CHAT,
                            text=f"✅ Confirmed {amount:,.0f} {currency} from {client}")
    return {"ok": True, "client": client, "amount": amount}


@tool(
    "payments.owner_reject",
    "Owner says the payment is not real. Client will be chased.",
    {"type": "object", "properties": {
        "client": {"type": "string"},
    }, "required": ["client"]},
)
async def owner_reject(client):
    from ..memory import Memory
    m = Memory()
    m.db.execute(
        """UPDATE pending_payments SET status='rejected'
           WHERE client=? AND status='awaiting_owner'""", (client,))
    m.db.commit()
    return {"ok": True, "client": client, "note": "will be chased"}


@tool(
    "payments.list_pending",
    "List payments waiting for owner confirmation.",
    {"type": "object", "properties": {}},
)
async def list_pending():
    from ..memory import Memory
    m = Memory()
    try:
        rows = m.db.execute(
            """SELECT client, amount, currency, ref, created
               FROM pending_payments
               WHERE status='awaiting_owner'
               ORDER BY created DESC""").fetchall()
    except Exception:
        return {"ok": True, "pending": []}
    return {"ok": True, "pending": [
        {"client": r[0], "amount": r[1], "currency": r[2],
         "ref": r[3], "when": r[4]} for r in rows]}

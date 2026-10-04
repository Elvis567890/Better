"""
BOAT brain.

Chat-first loop: every message is classified as chat / execute / confirm.
Chat replies instantly. Execute runs the task loop. Confirm handles
payment verifications.

Telegram destination is resolved automatically:
  1. If reply_to is passed in (from webhook/dispatch), use it.
  2. Otherwise fall back to TELEGRAM_ALLOWED (your chat id) from env.
This means you never have to type the chat_id manually.
"""
import asyncio
import json
import logging
import os
import time
import uuid

from .memory import Memory
from .planner import Planner
from .tools import call_tool, tool_specs, load_all


log = logging.getLogger("boat.brain")

BATCH = 4
MAX_ITER = 12
DAILY_GOAL = float(os.environ.get("BOAT_DAILY_GOAL", "10"))

# First entry of TELEGRAM_ALLOWED (comma-separated) becomes the default chat
DEFAULT_CHAT = (os.environ.get("TELEGRAM_ALLOWED", "").split(",")[0].strip()
                or "")


def _resolve_chat(reply_to):
    """Pick a chat id: explicit one wins, else the default from env."""
    if reply_to:
        return str(reply_to).strip()
    return DEFAULT_CHAT


class Boat:
    def __init__(self, memory=None, planner=None):
        load_all()
        self.memory = memory or Memory()
        self.planner = planner or Planner()

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    async def handle(self, command, source="github", reply_to=None):
        chat = _resolve_chat(reply_to)

        # record what the owner said
        self.memory.add_chat("owner", command)

        # context for the classifier
        history = self.memory.recent_chat(12)

        # 1. classify: chat / execute / confirm
        try:
            decision = await self.planner.classify(command, history)
        except Exception as e:
            log.exception("classify failed")
            decision = {"mode": "chat",
                        "reply": f"I couldn't think just now ({e}). Try again?"}

        mode = decision.get("mode", "chat")
        reply = decision.get("reply", "")

        if reply:
            await self._say(chat, reply)
            self.memory.add_chat("boat", reply)

        if mode == "chat":
            return {"mode": "chat", "reply": reply, "chat": chat}

        if mode == "confirm":
            return await self._handle_confirm(decision, chat)

        # execute
        task = decision.get("task") or command
        return await self._execute(task, source=source, reply_to=chat)

    # ------------------------------------------------------------------
    # Confirm mode — payment confirmations
    # ------------------------------------------------------------------
    async def _handle_confirm(self, decision, chat):
        action = (decision.get("confirm_action") or "").strip()
        low = action.lower()

        if low.startswith("yes"):
            client = action.split(" ", 1)[1].strip() if " " in action else ""
            try:
                r = await call_tool("payments.owner_confirm",
                                    {"client": client})
            except Exception as e:
                r = {"ok": False, "error": str(e)}
            await self._say(chat, f"Confirmed: {r}")
            return {"mode": "confirm", "result": r}

        if low.startswith("no"):
            client = action.split(" ", 1)[1].strip() if " " in action else ""
            try:
                r = await call_tool("payments.owner_reject",
                                    {"client": client})
            except Exception as e:
                r = {"ok": False, "error": str(e)}
            await self._say(chat, f"Rejected: {r}")
            return {"mode": "confirm", "result": r}

        await self._say(chat, "I didn't understand that confirmation.")
        return {"mode": "confirm",
                "result": {"ok": False, "reason": "unrecognized"}}

    # ------------------------------------------------------------------
    # Execute mode — scan, decide, act, pivot
    # ------------------------------------------------------------------
    async def _execute(self, command, source, reply_to):
        mid = uuid.uuid4().hex[:10]
        self.memory.create_mission(mid, command, source)

        mission = {
            "id": mid,
            "command": command,
            "steps_done": [],
            "pivots": 0,
            "money_today": self.memory.money_today(),
            "status": "scanning",
        }

        # ---- SCAN ----
        try:
            scan = await self.planner.scan(
                command, self.memory.recent_context())
        except Exception as e:
            scan = {"error": str(e), "today_opportunities": []}

        for op in scan.get("today_opportunities", [])[:10]:
            try:
                self.memory.add_opportunity(
                    op.get("title", "")[:200],
                    op.get("url", ""),
                    op.get("pays_today", False),
                    float(op.get("cost", 0) or 0),
                    float(op.get("eta_hours", 1) or 1),
                    op.get("notes", "")[:300],
                )
            except Exception:
                pass

        mission["scan"] = scan

        # ---- DECIDE ----
        try:
            decision = await self.planner.decide(
                command, scan, tool_specs())
        except Exception as e:
            return self._finish(mid, "planning_failed",
                                {"error": str(e)}, reply_to)

        plan = (decision.get("steps") or [])[:BATCH]

        results_all = []

        # ---- ACT / VERIFY / PIVOT ----
        for it in range(MAX_ITER):
            if not plan:
                break

            self.memory.update_mission(mid, status="acting")

            results = await asyncio.gather(
                *[self._run_step(s) for s in plan],
                return_exceptions=True,
            )
            norm = [r if isinstance(r, dict) else {"error": str(r)}
                    for r in results]
            results_all.extend(norm)

            for s, r in zip(plan, norm):
                mission["steps_done"].append({
                    "tool": s.get("tool"),
                    "why": s.get("why", ""),
                    "ok": r.get("ok", True),
                    "result": _trim(r),
                })

            # ask the planner what next
            try:
                nxt = await self.planner.next(
                    command, mission, norm, tool_specs())
            except Exception as e:
                nxt = {"done": True, "summary": f"planner error: {e}"}

            # planner wants input
            if nxt.get("ask"):
                try:
                    await call_tool("telegram.ask", {
                        "chat_id": str(reply_to),
                        "question": nxt["ask"],
                        "mission_id": mid,
                    })
                except Exception:
                    pass
                return self._finish(mid, "awaiting_input",
                                    {"question": nxt["ask"]}, reply_to)

            # planner wants to pivot
            if nxt.get("pivot"):
                mission["pivots"] += 1
                self.memory.update_mission(mid, pivots=mission["pivots"])
                try:
                    piv = await self.planner.pivot(
                        command, mission, tool_specs())
                except Exception as e:
                    piv = {"steps": [], "error": str(e)}
                plan = (piv.get("steps") or [])[:BATCH]
                continue

            # done
            if nxt.get("done"):
                return self._finish(
                    mid, "done",
                    {"summary": nxt.get("summary", ""),
                     "results": results_all},
                    reply_to)

            plan = (nxt.get("steps") or [])[:BATCH]

        return self._finish(mid, "max_iterations",
                            {"results": results_all}, reply_to)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _run_step(self, step):
        name = step.get("tool")
        args = step.get("args") or {}
        t0 = time.time()
        try:
            res = await call_tool(name, args)
            return {"tool": name, "ok": True,
                    "ms": int((time.time() - t0) * 1000),
                    "result": res}
        except Exception as e:
            log.exception("tool %s failed", name)
            return {"tool": name, "ok": False, "error": str(e),
                    "ms": int((time.time() - t0) * 1000)}

    async def _say(self, chat_id, text):
        """Send to Telegram. Falls back to DEFAULT_CHAT automatically."""
        chat = _resolve_chat(chat_id)
        log.info("BOAT> %s", text)
        if not chat:
            log.warning("No chat id available; skipping Telegram send")
            return
        try:
            await call_tool("telegram.send",
                            {"chat_id": str(chat), "text": text})
        except Exception as e:
            log.warning("telegram send failed: %s", e)

    def _finish(self, mid, status, payload, reply_to):
        self.memory.update_mission(
            mid, status=status, money_today=self.memory.money_today())
        summary = json.dumps(payload)[:900]
        self.memory.add_chat("boat", f"[{status}] {summary}")
        asyncio.create_task(self._say(
            reply_to, f"[{status}] {summary}"))
        return {"mission_id": mid, "status": status, **payload}


def _trim(r, n=800):
    try:
        s = json.dumps(r)
        return json.loads(s if len(s) <= n else s[:n] + '..."')
    except Exception:
        return str(r)[:n]

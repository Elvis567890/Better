import asyncio, json, logging, os, time, uuid

from .memory import Memory
from .planner import Planner
from .tools import call_tool, tool_specs, load_all

log = logging.getLogger("boat.brain")
BATCH = 4
MAX_ITER = 12
DAILY_GOAL = float(os.environ.get("BOAT_DAILY_GOAL", "10"))

class Boat:
    def __init__(self, memory=None, planner=None):
        load_all()
        self.memory = memory or Memory()
        self.planner = planner or Planner()

    async def handle(self, command, source="github", reply_to=None):
        mid = uuid.uuid4().hex[:10]
        self.memory.create_mission(mid, command, source)
        await self._say(reply_to, f"BOAT engaged - {command} (mission {mid})")

        mission = {"id": mid, "command": command, "steps_done": [],
                   "pivots": 0, "money_today": self.memory.money_today(),
                   "status": "scanning"}

        try:
            scan = await self.planner.scan(command, self.memory.recent_context())
        except Exception as e:
            scan = {"error": str(e), "today_opportunities": []}
        for op in scan.get("today_opportunities", [])[:10]:
            self.memory.add_opportunity(op.get("title", "")[:200], op.get("url", ""),
                                        op.get("pays_today", False),
                                        float(op.get("cost", 0) or 0),
                                        float(op.get("eta_hours", 1) or 1),
                                        op.get("notes", "")[:300])
        mission["scan"] = scan
        await self._say(reply_to, f"Scanned {len(scan.get('today_opportunities', []))} today-opportunities.")

        try:
            decision = await self.planner.decide(command, scan, tool_specs())
        except Exception as e:
            return self._finish(mid, "planning_failed", {"error": str(e)}, reply_to)
        plan = decision.get("steps", [])[:BATCH]
        await self._say(reply_to, f"Plan: {decision.get('plan_name','default')} - {len(plan)} steps.")

        results_all = []
        for it in range(MAX_ITER):
            if not plan: break
            mission["status"] = "acting"
            self.memory.update_mission(mid, status="acting")

            results = await asyncio.gather(*[self._run_step(s) for s in plan], return_exceptions=True)
            norm = [r if isinstance(r, dict) else {"error": str(r)} for r in results]
            results_all.extend(norm)
            for s, r in zip(plan, norm):
                mission["steps_done"].append({"tool": s.get("tool"), "why": s.get("why", ""),
                                              "ok": r.get("ok", True), "result": _trim(r)})

            paid = await self._verify(mid, reply_to)
            if paid:
                mission["status"] = "paid"
                self.memory.update_mission(mid, status="paid", money_today=self.memory.money_today())
                self.memory.add_lesson(mid, "paid", f"payment verified for: {command}")

            if not paid and self.memory.money_today() < DAILY_GOAL and it >= 1:
                mission["pivots"] += 1
                self.memory.update_mission(mid, pivots=mission["pivots"])
                try:
                    piv = await self.planner.pivot(command, mission, tool_specs())
                except Exception as e:
                    piv = {"steps": [], "error": str(e)}
                new_plan = piv.get("steps", [])[:BATCH]
                if new_plan:
                    await self._say(reply_to, f"No money today -> pivoting to {piv.get('plan_name','Plan B')}")
                    self.memory.add_lesson(mid, "pivot", f"pivoted: {piv.get('plan_name','')}")
                plan = new_plan
                continue

            try:
                nxt = await self.planner.next(command, mission, norm, tool_specs())
            except Exception as e:
                nxt = {"done": True, "summary": f"planner error: {e}"}
            if nxt.get("done"):
                return self._finish(mid, "done",
                                    {"summary": nxt.get("summary", ""), "results": results_all},
                                    reply_to)
            plan = (nxt.get("steps") or [])[:BATCH]

        return self._finish(mid, "max_iterations", {"results": results_all}, reply_to)

    async def _run_step(self, step):
        name = step.get("tool"); args = step.get("args") or {}
        t0 = time.time()
        try:
            res = await call_tool(name, args)
            return {"tool": name, "ok": True, "ms": int((time.time()-t0)*1000), "result": res}
        except Exception as e:
            log.exception("tool %s failed", name)
            return {"tool": name, "ok": False, "error": str(e), "ms": int((time.time()-t0)*1000)}

    async def _verify(self, mid, reply_to):
        found = False
        try:
            g = await call_tool("gmail.find_payments", {"since_days": 1})
            for h in g.get("hits", []):
                for a in h.get("amounts", []):
                    try: amt = float(str(a).replace(",", ""))
                    except ValueError: continue
                    self.memory.record_payment(mid, "gmail", amt, "USD", ref=h.get("subject", "")[:80], verified=1)
                    found = True
        except Exception as e:
            log.debug("gmail verify skipped: %s", e)
        try:
            m = await call_tool("momo.recent", {"limit": 10})
            if m.get("ok") and m.get("body"):
                self.memory.record_payment(mid, "momo", 0.0, "UGX", ref=str(m.get("body"))[:80], verified=1)
                found = True
        except Exception as e:
            log.debug("momo verify skipped: %s", e)
        try:
            s = await call_tool("phone.sms", {"limit": 20})
            for msg in s.get("messages", []):
                blob = (msg.get("body") or "").lower()
                if any(k in blob for k in ("received", "paid", "mpesa", "momo", "deposit")):
                    self.memory.record_payment(mid, "sms", 0.0, "UGX", ref=(msg.get("body") or "")[:80], verified=1)
                    found = True; break
        except Exception as e:
            log.debug("sms verify skipped: %s", e)
        if found:
            await self._say(reply_to, f"Payment verified. Today total: {self.memory.money_today()}")
        return found

    async def _say(self, chat_id, text):
        log.info("BOAT> %s", text)
        if chat_id:
            try: await call_tool("telegram.send", {"chat_id": str(chat_id), "text": text})
            except Exception: pass

    def _finish(self, mid, status, payload, reply_to):
        self.memory.update_mission(mid, status=status, money_today=self.memory.money_today())
        asyncio.create_task(self._say(reply_to, f"Mission {mid} -> {status}\n{json.dumps(payload)[:900]}"))
        return {"mission_id": mid, "status": status, **payload}

def _trim(r, n=800):
    try:
        s = json.dumps(r)
        return json.loads(s if len(s) <= n else s[:n] + '..."')
    except Exception:
        return str(r)[:n]

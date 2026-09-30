import json, os, re
import httpx

SYSTEM = """You are BOAT - an autonomous hustler agent.
Rules:
1. ZERO-COST and MONEY-TODAY beat future money.
2. Never wait on a human. If a step needs a human, pick another step.
3. Act in parallel. Return up to 4 steps per batch.
4. Verify payments before delivering work (gmail + momo + sms).
5. If Plan A makes no money today, PIVOT to Plan B anywhere on the internet.
6. Emit JSON only. No prose outside the JSON object."""

class Planner:
    def __init__(self, base=None, key=None, model=None):
        self.base = base or os.environ.get("BOAT_LLM_BASE", "https://api.openai.com/v1")
        self.key = key or os.environ.get("BOAT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get("BOAT_LLM_MODEL", "gpt-4o-mini")

    async def _chat(self, messages, max_tokens=1200):
        async with httpx.AsyncClient(timeout=90) as c:
            r = await c.post(f"{self.base}/chat/completions",
                             headers={"Authorization": f"Bearer {self.key}"},
                             json={"model": self.model, "messages": messages,
                                   "temperature": 0.4, "max_tokens": max_tokens,
                                   "response_format": {"type": "json_object"}})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _json(s):
        try: return json.loads(s)
        except Exception:
            m = re.search(r"\{.*\}", s, re.S)
            return json.loads(m.group(0)) if m else {}

    async def scan(self, command, context):
        msg = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"""
PHASE: SCAN.
Command: "{command}"
Memory: {json.dumps(context)[:3000]}
List available resources and 5 concrete today-opportunities on the internet where THIS command makes money TODAY at zero cost.
Return JSON: {{"resources":[...], "today_opportunities":[{{"title":..,"url":..,"pays_today":true,"cost":0,"eta_hours":1,"notes":..}}]}}
"""}]
        return self._json(await self._chat(msg))

    async def decide(self, command, scan, tools):
        msg = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"""
PHASE: DECIDE.
Command: "{command}"
Scan: {json.dumps(scan)[:4000]}
Tools: {json.dumps([t["name"] for t in tools])}
First parallel batch (<=4 steps) that moves money TODAY at zero cost.
Return JSON: {{"plan_name":"...","steps":[{{"tool":"...","args":{{}},"why":"..."}}]}}
"""}]
        return self._json(await self._chat(msg))

    async def next(self, command, mission, last_results, tools):
        msg = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"""
PHASE: NEXT.
Command: "{command}"
Mission: {json.dumps(mission)[:4000]}
Last batch results: {json.dumps(last_results)[:4000]}
Tools: {json.dumps([t["name"] for t in tools])}
Return one of:
  {{"done":true,"summary":"..."}}
  {{"steps":[...]}}
  {{"pivot":true,"reason":"..."}}
"""}]
        return self._json(await self._chat(msg))

    async def pivot(self, command, mission, tools):
        msg = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"""
PHASE: PIVOT.
Command: "{command}"
Failed approach: {json.dumps(mission)[:3500]}
Tools: {json.dumps([t["name"] for t in tools])}
Plan A made no money today. Invent Plan B - a DIFFERENT path that pays TODAY at zero cost.
Return JSON: {{"plan_name":"...","steps":[{{"tool":"...","args":{{}},"why":"..."}}]}}
"""}]
        return self._json(await self._chat(msg))

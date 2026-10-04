"""LLM planner. Classifies messages, thinks, decides, pivots."""
import json
import os
import re

import httpx


SYSTEM = """You are BOAT - an autonomous hustler agent that works for one
owner. You think like a hustler: ZERO-COST and MONEY-TODAY beat future money.
You never wait on a human unless a real human decision is required.

You have three modes:
  CHAT      - discuss a plan, answer a question, refine what the owner wants
  EXECUTE   - the owner has told you to do something; run the task loop
  CONFIRM   - the owner is confirming or rejecting something you asked about

You emit JSON only. No prose outside the JSON object."""


class Planner:
    def __init__(self, base=None, key=None, model=None):
        self.base = base or os.environ.get(
            "BOAT_LLM_BASE", "https://openrouter.ai/api/v1")
        self.key = (key
                    or os.environ.get("BOAT_LLM_KEY")
                    or os.environ.get("OPENAI_API_KEY"))
        self.model = model or os.environ.get(
            "BOAT_LLM_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

    async def _chat(self, messages, max_tokens=1200, temperature=0.4):
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                f"{self.base}/chat/completions",
                headers={"Authorization": f"Bearer {self.key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _json(s):
        try:
            return json.loads(s)
        except Exception:
            m = re.search(r"\{.*\}", s, re.S)
            return json.loads(m.group(0)) if m else {}

    # ---------- CLASSIFY ----------
    async def classify(self, message, history):
        hist = "\n".join(
            f"{h.get('role','?')}: {h.get('text','')}" for h in history[-10:]
        )
        prompt = f"""Recent conversation:
{hist}

New message from owner: "{message}"

Decide:
- If the owner is chatting, asking a question, brainstorming, or clarifying
  what they want -> mode = "chat". Provide a short natural reply.
- If the owner is telling you to DO something that needs actual work
  (build, find, send, make money, register, check, write, post, search,
  create, collect, sell, pitch, contact...) -> mode = "execute".
- If the owner is confirming/rejecting something you previously asked
  ("yes", "no", "go ahead", "cancel", "yes <name>") -> mode = "confirm".

Be generous with "execute" — if the owner seems to want an action,
treat it as execute. Chat only when they are clearly just talking.

Return JSON only:
{{
  "mode": "chat" | "execute" | "confirm",
  "reply": "short natural reply to the owner",
  "task": "if mode=execute, the cleaned-up task description",
  "confirm_action": "yes <name>" | "no <name>" | ""
}}"""
        raw = await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=600, temperature=0.3,
        )
        return self._json(raw)

    # ---------- SCAN ----------
    async def scan(self, command, context):
        prompt = f"""PHASE: SCAN.
Command: "{command}"
Memory: {json.dumps(context)[:3000]}

List available resources and 5 concrete today-opportunities on the internet
where THIS command can produce a result or make money TODAY at zero cost.

Return JSON:
{{"resources": [...],
  "today_opportunities": [
    {{"title": "..", "url": "..", "pays_today": true, "cost": 0,
      "eta_hours": 1, "notes": ".."}}
  ]}}"""
        raw = await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
        )
        return self._json(raw)

    # ---------- DECIDE ----------
    async def decide(self, command, scan, tools):
        prompt = f"""PHASE: DECIDE.
Command: "{command}"
Scan: {json.dumps(scan)[:4000]}
Available tools: {json.dumps([t["name"] for t in tools])}

Pick the FIRST parallel batch (max 4 steps) that moves toward the goal.
If the task is to build something, use code.write_flutter_app then code.build_apk.
If the task is to find work, use browser.open + research tools.
If the task is to write text, use the LLM directly by returning no tools and
putting the answer in the "summary" field of a done step.

Return JSON:
{{"plan_name": "...",
  "steps": [{{"tool": "...", "args": {{}}, "why": "..."}}]}}"""
        raw = await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
        )
        return self._json(raw)

    # ---------- NEXT ----------
    async def next(self, command, mission, last_results, tools):
        prompt = f"""PHASE: NEXT.
Command: "{command}"
Mission so far: {json.dumps(mission)[:4000]}
Last batch results: {json.dumps(last_results)[:4000]}
Available tools: {json.dumps([t["name"] for t in tools])}

Decide one of:
  {{"done": true, "summary": "what was accomplished"}}
  {{"steps": [{{"tool": "...", "args": {{}}, "why": "..."}}]}}
  {{"pivot": true, "reason": "why Plan A failed"}}
  {{"ask": "question for the owner"}}
"""
        raw = await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
        )
        return self._json(raw)

    # ---------- PIVOT ----------
    async def pivot(self, command, mission, tools):
        prompt = f"""PHASE: PIVOT.
Command: "{command}"
Failed approach: {json.dumps(mission)[:3500]}
Available tools: {json.dumps([t["name"] for t in tools])}

Plan A did not work. Invent Plan B - a DIFFERENT path toward the same goal.

Return JSON:
{{"plan_name": "...",
  "steps": [{{"tool": "...", "args": {{}}, "why": "..."}}]}}"""
        raw = await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
        )
        return self._json(raw)

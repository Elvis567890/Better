"""LLM planner. Auto-detects Gemini (native) vs OpenAI-compatible providers."""
import json
import os
import re

import httpx


SYSTEM = """You are BOAT - an autonomous hustler agent that works for one
owner. You think like a hustler: ZERO-COST and MONEY-TODAY beat future money.
You never wait on a human unless a real human decision is required.

Modes:
  CHAT      - discuss, answer, refine what the owner wants
  EXECUTE   - the owner told you to do something; run the task loop
  CONFIRM   - the owner is confirming or rejecting something you asked about

Emit JSON only. No prose outside the JSON object."""


class Planner:
    def __init__(self, base=None, key=None, model=None):
        self.base = (base or os.environ.get(
            "BOAT_LLM_BASE", "https://openrouter.ai/api/v1")).rstrip("/")
        self.key = (key
                    or os.environ.get("BOAT_LLM_KEY")
                    or os.environ.get("OPENAI_API_KEY"))
        self.model = model or os.environ.get(
            "BOAT_LLM_MODEL", "gemini-flash-latest")

        if "generativelanguage.googleapis.com" in self.base:
            self.provider = "gemini"
        else:
            self.provider = "openai"

    # ------------------------------------------------------------------
    # Provider dispatch
    # ------------------------------------------------------------------
    async def _chat(self, messages, max_tokens=1200, temperature=0.4):
        if self.provider == "gemini":
            return await self._gemini(messages, max_tokens, temperature)
        return await self._openai(messages, max_tokens, temperature)

    async def _openai(self, messages, max_tokens, temperature):
        url = f"{self.base}/chat/completions"
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                url,
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

    async def _gemini(self, messages, max_tokens, temperature):
        system_text = ""
        contents = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_text += content + "\n"
            else:
                g_role = "user" if role == "user" else "model"
                contents.append({
                    "role": g_role,
                    "parts": [{"text": content}],
                })

        base = self.base
        if base.endswith("/openai"):
            base = base[: -len("/openai")]

        url = f"{base}/models/{self.model}:generateContent"

        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }
        if system_text.strip():
            body["systemInstruction"] = {
                "parts": [{"text": system_text.strip()}],
            }

        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.key,
                },
                json=body,
            )
            if r.status_code >= 400:
                raise RuntimeError(
                    f"gemini {r.status_code}: {r.text[:300]}"
                )
            j = r.json()
            return j["candidates"][0]["content"]["parts"][0]["text"]

    @staticmethod
    def _json(s):
        try:
            return json.loads(s)
        except Exception:
            m = re.search(r"\{.*\}", s, re.S)
            return json.loads(m.group(0)) if m else {}

    # ------------------------------------------------------------------
    # Classify
    # ------------------------------------------------------------------
    async def classify(self, message, history):
        hist = "\n".join(
            f"{h.get('role','?')}: {h.get('text','')}" for h in history[-10:]
        )
        prompt = f"""Recent conversation:
{hist}

New message from owner: "{message}"

Decide:
- Chatting, asking, brainstorming -> mode = "chat" with short reply.
- Told to DO something (build, find, send, make money, register, check,
  write, post, search, create, collect, sell, pitch, contact) -> "execute".
- Confirming/rejecting a previous ask ("yes", "no", "yes <name>") -> "confirm".

Return JSON only:
{{
  "mode": "chat" | "execute" | "confirm",
  "reply": "short natural reply",
  "task": "if mode=execute, cleaned-up task",
  "confirm_action": "yes <name>" | "no <name>" | ""
}}"""
        raw = await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=600, temperature=0.3,
        )
        return self._json(raw)

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------
    async def scan(self, command, context):
        prompt = f"""PHASE: SCAN.
Command: "{command}"
Memory: {json.dumps(context)[:3000]}

List 5 concrete today-opportunities on the internet where THIS command can
produce a result or make money TODAY at zero cost.

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

    # ------------------------------------------------------------------
    # Decide
    # ------------------------------------------------------------------
    async def decide(self, command, scan, tools):
        prompt = f"""PHASE: DECIDE.
Command: "{command}"
Scan: {json.dumps(scan)[:4000]}
Tools: {json.dumps([t["name"] for t in tools])}

Pick the FIRST parallel batch (max 4 steps) toward the goal.
- Build task -> code.write_flutter_app then code.build_apk
- Find task -> browser.open + research tools
- Write task -> return no tools and put the text in a done step.

Return JSON:
{{"plan_name": "...",
  "steps": [{{"tool": "...", "args": {{}}, "why": "..."}}]}}"""
        raw = await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
        )
        return self._json(raw)

    # ------------------------------------------------------------------
    # Next
    # ------------------------------------------------------------------
    async def next(self, command, mission, last_results, tools):
        prompt = f"""PHASE: NEXT.
Command: "{command}"
Mission: {json.dumps(mission)[:4000]}
Last results: {json.dumps(last_results)[:4000]}
Tools: {json.dumps([t["name"] for t in tools])}

Return one of:
  {{"done": true, "summary": "what was accomplished"}}
  {{"steps": [{{"tool": "...", "args": {{}}, "why": "..."}}]}}
  {{"pivot": true, "reason": "why Plan A failed"}}
  {{"ask": "question for the owner"}}"""
        raw = await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
        )
        return self._json(raw)

    # ------------------------------------------------------------------
    # Pivot
    # ------------------------------------------------------------------
    async def pivot(self, command, mission, tools):
        prompt = f"""PHASE: PIVOT.
Command: "{command}"
Failed approach: {json.dumps(mission)[:3500]}
Tools: {json.dumps([t["name"] for t in tools])}

Plan A did not work. Invent Plan B - a DIFFERENT path to the same goal.

Return JSON:
{{"plan_name": "...",
  "steps": [{{"tool": "...", "args": {{}}, "why": "..."}}]}}"""
        raw = await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
        )
        return self._json(raw)

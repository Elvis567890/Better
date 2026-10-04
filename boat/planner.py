"""LLM planner with automatic provider + model discovery.

Flow:
  1. Read BOAT_LLM_KEY (whatever provider).
  2. Detect provider from the key prefix.
  3. Ask the provider GET /models for its live list.
  4. Filter to chat-capable models.
  5. Try each until one answers.
  6. Remember the winner in boat.db.
"""
import json
import os
import re
import asyncio
import httpx

try:
    from .memory import Memory
except Exception:
    Memory = None


SYSTEM = """You are BOAT - an autonomous hustler agent.
Reply with a single valid JSON object. No prose. No markdown fences.
Inside the "reply" field, write a COMPLETE answer. If you list ideas,
include all of them. Never stop mid-sentence."""


PROVIDERS = [
    {
        "name": "groq",
        "prefix": "gsk_",
        "base": "https://api.groq.com/openai/v1",
        "preferred": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
            "meta-llama/llama-4-scout-17b-16e-instruct",
        ],
    },
    {
        "name": "cerebras",
        "prefix": "csk-",
        "base": "https://api.cerebras.ai/v1",
        "preferred": ["llama-3.3-70b", "llama3.1-8b"],
    },
    {
        "name": "openrouter",
        "prefix": "sk-or-v1-",
        "base": "https://openrouter.ai/api/v1",
        "preferred": [],
        "free_only": True,
    },
    {
        "name": "aimlapi",
        "prefix": "24b",
        "base": "https://api.aimlapi.com/v1",
        "preferred": ["inclusionai/ling-3.0-tiny"],
    },
]


class Planner:
    def __init__(self, base=None, key=None, model=None):
        keys = []
        for env in ("BOAT_LLM_KEY", "GROQ_KEY", "CEREBRAS_KEY",
                    "OPENROUTER_KEY", "AIMLAPI_KEY"):
            k = os.environ.get(env)
            if k:
                keys.append(k.strip())
        if key:
            keys.insert(0, key.strip())
        if not keys:
            raise RuntimeError("No LLM key found. Set BOAT_LLM_KEY.")

        self.chain = []
        seen = set()
        for k in keys:
            p = self._detect(k)
            if not p or p["base"] in seen:
                continue
            seen.add(p["base"])
            self.chain.append({**p, "key": k, "models": None})

        if not self.chain:
            raise RuntimeError(
                "Unrecognized key prefix. Supported: "
                "gsk_ (Groq), csk- (Cerebras), sk-or-v1- (OpenRouter), "
                "24b (AIMLAPI).")

        self._memo = Memory() if Memory else None
        self._winner = None
        if self._memo:
            try:
                self._winner = self._memo.kv_get("llm.winner")
            except Exception:
                self._winner = None

    @staticmethod
    def _detect(key):
        for p in PROVIDERS:
            if key.startswith(p["prefix"]):
                return dict(p)
        return None

    async def _discover(self, provider):
        """Fetch the live model list from the provider."""
        url = f"{provider['base']}/models"
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.get(
                    url,
                    headers={"Authorization": f"Bearer {provider['key']}"})
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            print(f"  [discover] {provider['name']} /models failed: {e}")
            return []

        items = data.get("data") or data.get("models") or []
        ids = []
        for m in items:
            mid = m.get("id") or m.get("name") or ""
            if not mid:
                continue
            if provider.get("free_only") and not mid.endswith(":free"):
                continue
            low = mid.lower()
            if any(x in low for x in ("whisper", "tts", "embed",
                                      "vision-only", "guard")):
                continue
            ids.append(mid)

        if not ids:
            return []

        pref = provider.get("preferred", [])
        ranked = []
        for want in pref:
            if want in ids:
                ranked.append(want)
        for mid in ids:
            if mid not in ranked:
                ranked.append(mid)
        print(f"  [discover] {provider['name']}: {len(ranked)} models, "
              f"top={ranked[0] if ranked else 'none'}")
        return ranked[:15]

    async def _chat(self, messages, max_tokens=2000, temperature=0.4):
        attempts = []

        if self._winner:
            for c in self.chain:
                if c["base"] == self._winner.get("base"):
                    attempts.append((c, self._winner["model"]))
                    break

        for c in self.chain:
            if c["models"] is None:
                c["models"] = await self._discover(c)
            for m in c["models"]:
                if (c, m) not in attempts:
                    attempts.append((c, m))

        if not attempts:
            raise RuntimeError("No models found on any provider.")

        last_error = None
        for provider, model in attempts:
            try:
                text = await self._call(provider, model, messages,
                                        max_tokens, temperature)
                if not text or not text.strip():
                    last_error = f"{provider['name']}/{model}: empty"
                    continue
                if self._memo:
                    try:
                        self._memo.kv_set("llm.winner",
                                          {"base": provider["base"],
                                           "model": model})
                    except Exception:
                        pass
                    self._winner = {"base": provider["base"], "model": model}
                print(f"  [llm] {provider['name']}/{model} OK")
                return text
            except Exception as e:
                last_error = f"{provider['name']}/{model}: {str(e)[:120]}"
                continue

        raise RuntimeError(f"Every model failed. Last: {last_error}")

    async def _call(self, provider, model, messages, max_tokens, temperature):
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                f"{provider['base']}/chat/completions",
                headers={"Authorization": f"Bearer {provider['key']}"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            if r.status_code in (429, 503):
                await asyncio.sleep(2)
                raise RuntimeError(f"{r.status_code} busy")
            r.raise_for_status()
            data = r.json()
            try:
                content = data["choices"][0]["message"].get("content")
            except Exception:
                content = None
            return content or ""

    @staticmethod
    def _json(s):
        if not s:
            return {}
        s = s.strip()
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
        try:
            return json.loads(s)
        except Exception:
            m = re.search(r"\{.*\}", s, re.S)
            if not m:
                return {}
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}

    # ---------- phases ----------
    async def classify(self, message, history):
        hist = "\n".join(f"{h.get('role','?')}: {h.get('text','')}"
                         for h in history[-10:])
        prompt = (
            f'Recent conversation:\n{hist}\n\n'
            f'New message from owner: "{message}"\n\n'
            'Decide mode:\n'
            '- If owner is chatting, asking, or brainstorming -> "chat".\n'
            '- If owner wants you to DO something -> "execute".\n'
            '- If owner is confirming/rejecting a previous ask -> "confirm".\n\n'
            'Reply ONLY with this JSON (no prose, no code fences):\n'
            '{\n'
            '  "mode": "chat" | "execute" | "confirm",\n'
            '  "reply": "your COMPLETE natural reply here. If you list '
            'items, include ALL of them. Never stop mid-sentence.",\n'
            '  "task": "cleaned-up task if mode=execute, else empty",\n'
            '  "confirm_action": "yes <name>" or "no <name>" or ""\n'
            '}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=2000, temperature=0.3))

    async def scan(self, command, context):
        prompt = (f'Command: "{command}"\n'
                  f'Memory: {json.dumps(context)[:1500]}\n\n'
                  'Reply ONLY JSON: {"resources":[],"today_opportunities":['
                  '{"title":"..","url":"..","pays_today":true,"cost":0,'
                  '"eta_hours":1}]}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=1500))

    async def decide(self, command, scan, tools):
        prompt = (f'Command: "{command}"\n'
                  f'Scan: {json.dumps(scan)[:1500]}\n'
                  f'Tools: {json.dumps([t["name"] for t in tools])}\n\n'
                  'Reply ONLY JSON: {"plan_name":"..",'
                  '"steps":[{"tool":"..","args":{},"why":".."}]}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=1500))

    async def next(self, command, mission, last_results, tools):
        prompt = (f'Command: "{command}"\n'
                  f'Mission: {json.dumps(mission)[:1500]}\n'
                  f'Results: {json.dumps(last_results)[:1500]}\n\n'
                  'Reply ONLY one of: {"done":true,"summary":".."} '
                  'or {"steps":[...]} or {"pivot":true,"reason":".."} '
                  'or {"ask":".."}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=1500))

    async def pivot(self, command, mission, tools):
        prompt = (f'Command: "{command}"\n'
                  f'Failed: {json.dumps(mission)[:1500]}\n\n'
                  'Reply ONLY JSON: {"plan_name":"..",'
                  '"steps":[{"tool":"..","args":{},"why":".."}]}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=1500))

    async def repair(self, command, mission, failed, tools):
        prompt = (f'Command: "{command}"\n'
                  f'Failed: {json.dumps(failed)[:1200]}\n\n'
                  'Reply ONLY JSON: {"plan_name":"..","steps":[...]} '
                  'or {"give_up":true,"reason":".."}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=1500))

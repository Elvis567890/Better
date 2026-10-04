"""LLM planner with auto-detected provider AND auto-discovered models.

- You give it ONE key.
- It detects the provider from the key prefix.
- It asks the provider "what models do you have?" at runtime.
- It picks a working one and remembers it.
- No hardcoded model names. Nothing to go stale.
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


SYSTEM = """You are BOAT - an autonomous hustler agent. Emit JSON only."""


# Provider recipes. `models_endpoint` = where to fetch the live list.
PROVIDERS = [
    {
        "name": "cerebras",
        "prefix": "csk-",
        "base": "https://api.cerebras.ai/v1",
        "fallback_models": ["llama-3.3-70b", "llama3.1-8b"],
    },
    {
        "name": "groq",
        "prefix": "gsk_",
        "base": "https://api.groq.com/openai/v1",
        "fallback_models": ["llama-3.3-70b-versatile",
                            "llama-3.1-8b-instant"],
    },
    {
        "name": "openrouter",
        "prefix": "sk-or-v1-",
        "base": "https://openrouter.ai/api/v1",
        "fallback_models": [
            "meta-llama/llama-3.3-70b-instruct:free",
            "deepseek/deepseek-chat:free",
        ],
        # OpenRouter's public models endpoint — we filter for ":free"
        "discover": True,
    },
    {
        "name": "aimlapi",
        "prefix": "24b",
        "base": "https://api.aimlapi.com/v1",
        "fallback_models": ["inclusionai/ling-3.0-tiny"],
    },
]


class Planner:
    def __init__(self, base=None, key=None, model=None):
        keys = []
        for env in ("BOAT_LLM_KEY", "CEREBRAS_KEY", "GROQ_KEY",
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
            self.chain.append({**p, "key": k,
                               "models": None})  # populated lazily

        if not self.chain:
            raise RuntimeError("Key prefix not recognized. Supported: "
                               "csk-, gsk_, sk-or-v1-, 24b")

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

    async def _discover_models(self, provider):
        """Ask the provider what models it has. Return ones we can use."""
        base = provider["base"]
        key = provider["key"]

        if provider.get("discover"):
            # OpenRouter: fetch all, keep the free ones
            try:
                async with httpx.AsyncClient(timeout=30) as c:
                    r = await c.get(f"{base}/models",
                                    headers={"Authorization": f"Bearer {key}"})
                    r.raise_for_status()
                    data = r.json().get("data", [])
                    free = [m["id"] for m in data
                            if m.get("id", "").endswith(":free")]
                    if free:
                        return free[:10]
            except Exception:
                pass

        # Fallback: use the hardcoded list for this provider
        return list(provider.get("fallback_models", []))

    async def _chat(self, messages, max_tokens=1200, temperature=0.4):
        attempts = []

        # winner first
        if self._winner:
            for c in self.chain:
                if c["base"] == self._winner.get("base"):
                    attempts.append((c, self._winner["model"]))
                    break

        # build the full list of (provider, model) attempts
        for c in self.chain:
            if c["models"] is None:
                c["models"] = await self._discover_models(c)
            for m in c["models"]:
                if (c, m) not in attempts:
                    attempts.append((c, m))

        last_error = None
        for provider, model in attempts:
            try:
                text = await self._call(provider, model, messages,
                                        max_tokens, temperature)
                if self._memo:
                    try:
                        self._memo.kv_set("llm.winner",
                                          {"base": provider["base"],
                                           "model": model})
                    except Exception:
                        pass
                    self._winner = {"base": provider["base"], "model": model}
                return text
            except Exception as e:
                last_error = f"{provider['name']}/{model}: {str(e)[:120]}"
                continue

        raise RuntimeError(f"Every provider failed. Last: {last_error}")

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
                    "response_format": {"type": "json_object"},
                },
            )
            if r.status_code in (429, 503):
                await asyncio.sleep(2)
                raise RuntimeError(f"{r.status_code} busy")
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _json(s):
        try:
            return json.loads(s)
        except Exception:
            m = re.search(r"\{.*\}", s, re.S)
            return json.loads(m.group(0)) if m else {}

    # ---------- phases ----------
    async def classify(self, message, history):
        hist = "\n".join(f"{h.get('role','?')}: {h.get('text','')}"
                         for h in history[-10:])
        prompt = (f'Conversation:\n{hist}\n\nNew message: "{message}"\n'
                  'Return JSON only: {"mode":"chat"|"execute"|"confirm",'
                  '"reply":"...","task":"...","confirm_action":"..."}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=600, temperature=0.3))

    async def scan(self, command, context):
        prompt = (f'SCAN. Command: "{command}"\n'
                  f'Memory: {json.dumps(context)[:2000]}\n'
                  'Return JSON: {"resources":[],"today_opportunities":['
                  '{"title":"..","url":"..","pays_today":true,"cost":0}]}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}]))

    async def decide(self, command, scan, tools):
        prompt = (f'DECIDE. Command: "{command}"\n'
                  f'Scan: {json.dumps(scan)[:2000]}\n'
                  f'Tools: {json.dumps([t["name"] for t in tools])}\n'
                  'Return JSON: {"plan_name":"..",'
                  '"steps":[{"tool":"..","args":{}}]}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}]))

    async def next(self, command, mission, last_results, tools):
        prompt = (f'NEXT. Command: "{command}"\n'
                  f'Mission: {json.dumps(mission)[:2000]}\n'
                  f'Results: {json.dumps(last_results)[:2000]}\n'
                  'Return JSON: {"done":true,"summary":".."} '
                  'or {"steps":[...]} or {"pivot":true,"reason":".."} '
                  'or {"ask":".."}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}]))

    async def pivot(self, command, mission, tools):
        prompt = (f'PIVOT. Command: "{command}"\n'
                  f'Failed: {json.dumps(mission)[:2000]}\n'
                  'Return JSON: {"plan_name":"..",'
                  '"steps":[{"tool":"..","args":{}}]}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}]))

    async def repair(self, command, mission, failed, tools):
        prompt = (f'REPAIR. Command: "{command}"\n'
                  f'Failed: {json.dumps(failed)[:1500]}\n'
                  'Return JSON: {"plan_name":"..","steps":[...]} '
                  'or {"give_up":true,"reason":".."}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}]))

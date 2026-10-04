"""LLM planner that auto-detects the provider from the key.

You provide ONE key (BOAT_LLM_KEY). That's all.
- It reads the key prefix to know which provider it is.
- It picks the correct base URL automatically.
- It picks a working free model automatically.
- It remembers the winner in boat.db so next time is instant.
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


SYSTEM = """You are BOAT - an autonomous hustler agent. Think like a hustler:
zero-cost and money-today beat future money. Emit JSON only."""


# Provider recipes — each one knows its key prefix, base URL, and candidate models.
# Order here = order of fallback if a provider fails.
PROVIDERS = [
    {
        "name": "cerebras",
        "prefix": "csk-",
        "base": "https://api.cerebras.ai/v1",
        "models": ["llama-3.3-70b", "llama3.1-8b"],
    },
    {
        "name": "groq",
        "prefix": "gsk_",
        "base": "https://api.groq.com/openai/v1",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
    },
    {
        "name": "openrouter",
        "prefix": "sk-or-v1-",
        "base": "https://openrouter.ai/api/v1",
        "models": [
            "meta-llama/llama-3.3-70b-instruct:free",
            "deepseek/deepseek-chat-v3.1:free",
            "google/gemini-2.0-flash-exp:free",
            "qwen/qwen-2.5-72b-instruct:free",
            "mistralai/mistral-small-3.1-24b-instruct:free",
        ],
    },
    {
        "name": "sambanova",
        "prefix": "sb_",
        "base": "https://api.sambanova.ai/v1",
        "models": ["Meta-Llama-3.3-70B-Instruct"],
    },
    {
        "name": "aimlapi",
        "prefix": "24b",  # AIMLAPI keys often start this way
        "base": "https://api.aimlapi.com/v1",
        "models": ["inclusionai/ling-3.0-tiny"],
    },
]


class Planner:
    def __init__(self, base=None, key=None, model=None):
        # Collect every key we can find (BOAT_LLM_KEY plus per-provider names).
        keys = []
        for env in ("BOAT_LLM_KEY", "CEREBRAS_KEY", "GROQ_KEY",
                    "OPENROUTER_KEY", "SAMBANOVA_KEY", "AIMLAPI_KEY"):
            k = os.environ.get(env)
            if k:
                keys.append(k.strip())

        if key:
            keys.insert(0, key.strip())

        if not keys:
            raise RuntimeError(
                "No LLM key found. Set BOAT_LLM_KEY in GitHub secrets.")

        # Build a chain: for each key, detect provider + all its models.
        self.chain = []
        seen_bases = set()
        for k in keys:
            provider = self._detect_from_key(k)
            if not provider:
                continue
            if provider["base"] in seen_bases:
                continue
            seen_bases.add(provider["base"])
            self.chain.append({
                "name": provider["name"],
                "base": provider["base"],
                "key": k,
                "models": list(provider["models"]),
            })

        if not self.chain:
            raise RuntimeError(
                "Could not recognize any key prefix. Supported: "
                "csk- (Cerebras), gsk_ (Groq), sk-or-v1- (OpenRouter), "
                "sb_ (SambaNova).")

        # Memory to remember the winner.
        self._memo = Memory() if Memory else None
        self._winner = None
        if self._memo:
            try:
                self._winner = self._memo.kv_get("llm.winner")
            except Exception:
                self._winner = None

    @staticmethod
    def _detect_from_key(key):
        for p in PROVIDERS:
            if key.startswith(p["prefix"]):
                return p
        return None

    async def _chat(self, messages, max_tokens=1200, temperature=0.4):
        attempts = []

        # winner first
        if self._winner:
            for c in self.chain:
                if c["base"] == self._winner.get("base"):
                    attempts.append((c, self._winner["model"]))
                    break

        # then everyone else
        for c in self.chain:
            for m in c["models"]:
                if (c, m) not in attempts:
                    attempts.append((c, m))

        last_error = None
        for provider, model in attempts:
            try:
                text = await self._call(provider, model, messages,
                                        max_tokens, temperature)
                if self._memo and (not self._winner
                                   or self._winner.get("base") != provider["base"]
                                   or self._winner.get("model") != model):
                    try:
                        self._memo.kv_set("llm.winner",
                                          {"base": provider["base"],
                                           "model": model,
                                           "name": provider["name"]})
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
        prompt = f"""Conversation:\n{hist}\n\nNew message: "{message}"\n
Return JSON only:
{{"mode": "chat"|"execute"|"confirm", "reply": "...",
  "task": "...", "confirm_action": "..."}}"""
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=600, temperature=0.3))

    async def scan(self, command, context):
        prompt = f"""SCAN. Command: "{command}"
Memory: {json.dumps(context)[:2500]}
Return JSON: {{"resources":[],"today_opportunities":[
  {{"title":"..","url":"..","pays_today":true,"cost":0,"eta_hours":1}}]}}"""
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}]))

    async def decide(self, command, scan, tools):
        prompt = f"""DECIDE. Command: "{command}"
Scan: {json.dumps(scan)[:2500]}
Tools: {json.dumps([t["name"] for t in tools])}
Return JSON: {{"plan_name":"..","steps":[{{"tool":"..","args":{{}}}}]}}"""
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}]))

    async def next(self, command, mission, last_results, tools):
        prompt = f"""NEXT. Command: "{command}"
Mission: {json.dumps(mission)[:2500]}
Results: {json.dumps(last_results)[:2500]}
Return one of:
  {{"done":true,"summary":".."}} / {{"steps":[..]}} /
  {{"pivot":true,"reason":".."}} / {{"ask":".."}}"""
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}]))

    async def pivot(self, command, mission, tools):
        prompt = f"""PIVOT. Command: "{command}"
Failed: {json.dumps(mission)[:2500]}
Return JSON: {{"plan_name":"..","steps":[{{"tool":"..","args":{{}}}}]}}"""
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}]))

    async def repair(self, command, mission, failed, tools):
        prompt = f"""REPAIR. Command: "{command}"
Failed: {json.dumps(failed)[:2000]}
Return JSON: {{"plan_name":"..","steps":[...]}}
OR {{"give_up":true,"reason":".."}}"""
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}]))

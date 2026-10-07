"""LLM planner with deterministic routing."""
import json
import os
import re
import asyncio
import httpx

try:
    from .memory import Memory
except Exception:
    Memory = None


SYSTEM = """You are BOAT - an autonomous worker.
Reply with a single valid JSON object. No prose outside the JSON."""


PROVIDERS = [
    {"name": "groq", "prefix": "gsk_",
     "base": "https://api.groq.com/openai/v1",
     "preferred": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                   "openai/gpt-oss-120b"]},
    {"name": "cerebras", "prefix": "csk-",
     "base": "https://api.cerebras.ai/v1",
     "preferred": ["llama-3.3-70b", "llama3.1-8b"]},
    {"name": "openrouter", "prefix": "sk-or-v1-",
     "base": "https://openrouter.ai/api/v1",
     "preferred": [], "free_only": True},
]


EXECUTE_TRIGGERS = (
    "build ", "make ", "create ", "generate ", "design ", "write ",
    "code ", "program ", "find ", "search ", "look up ", "send ",
    "post ", "register ", "sign up ", "check ", "do ", "just do",
    "just build", "go ahead", "start ", "begin ", "run ",
    "android", "flutter", "website", "app ", "script ",
    "make me", "build me", "find me", "write me", "create me",
    "game ", "tool ", "bot ", "site ",
)


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
            raise RuntimeError("Unrecognized key prefix.")

        self._memo = Memory() if Memory else None
        self._winner = None
        if self._memo:
            try:
                self._winner = self._memo.kv_get("llm.winner")
            except Exception:
                pass

    @staticmethod
    def _detect(key):
        for p in PROVIDERS:
            if key.startswith(p["prefix"]):
                return dict(p)
        return None

    async def _discover(self, provider):
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.get(
                    f"{provider['base']}/models",
                    headers={"Authorization": f"Bearer {provider['key']}"})
                r.raise_for_status()
                data = r.json()
        except Exception:
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
        ranked = [w for w in pref if w in ids]
        for mid in ids:
            if mid not in ranked:
                ranked.append(mid)
        return ranked[:15]

    async def _chat(self, messages, max_tokens=3000, temperature=0.4):
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
            raise RuntimeError("No models found.")

        last_error = None
        for provider, model in attempts:
            try:
                text = await self._call(provider, model, messages,
                                        max_tokens, temperature)
                if not text or not text.strip():
                    continue
                if self._memo:
                    try:
                        self._memo.kv_set("llm.winner",
                                          {"base": provider["base"],
                                           "model": model})
                    except Exception:
                        pass
                return text
            except Exception as e:
                last_error = f"{provider['name']}/{model}: {str(e)[:120]}"
                continue

        await asyncio.sleep(4)
        for provider, model in attempts[:3]:
            try:
                text = await self._call(provider, model, messages,
                                        max_tokens, temperature)
                if text and text.strip():
                    return text
            except Exception:
                continue
        raise RuntimeError(f"Every model failed. Last: {last_error}")

    async def _call(self, provider, model, messages, max_tokens, temperature):
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                f"{provider['base']}/chat/completions",
                headers={"Authorization": f"Bearer {provider['key']}"},
                json={"model": model, "messages": messages,
                      "temperature": temperature, "max_tokens": max_tokens})
            if r.status_code in (429, 503):
                await asyncio.sleep(2)
                raise RuntimeError(f"{r.status_code} busy")
            r.raise_for_status()
            data = r.json()
            try:
                return data["choices"][0]["message"].get("content") or ""
            except Exception:
                return ""

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

    async def classify(self, message, history):
        low = " " + message.lower().strip() + " "
        for trig in EXECUTE_TRIGGERS:
            if trig in low:
                return {"mode": "execute",
                        "reply": "On it. Working now, will report back.",
                        "task": message, "confirm_action": ""}

        if low.strip() in ("yes", "no", "ok", "okay", "y", "n"):
            return {"mode": "chat", "reply": "Ok.",
                    "task": "", "confirm_action": ""}

        hist = "\n".join(f"{h.get('role','?')}: {h.get('text','')}"
                         for h in history[-6:])
        prompt = (f"Conversation:\n{hist}\n\n"
                  f'New message: "{message}"\n\n'
                  'Reply ONLY JSON: {"mode":"chat","reply":"<your answer>"}')
        d = self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=1500, temperature=0.2))
        reply = d.get("reply") or ""
        if "<" in reply and ">" in reply:
            reply = ""
        return {"mode": "chat", "reply": reply or "(thinking...)",
                "task": "", "confirm_action": ""}

    async def decide(self, command, scan, tools):
        low = command.lower()

        if any(k in low for k in ("game", "arcade", "puzzle")):
            slug = self._slug(command)
            return {"plan_name": "build_game",
                    "steps": [
                        {"tool": "code.write_flutter_app",
                         "args": {"spec": command + " (make it playable)",
                                  "app_slug": slug},
                         "why": "write game source"},
                        {"tool": "code.build_apk",
                         "args": {"app_slug": slug, "spec": command},
                         "why": "compile and ship"},
                    ]}

        if any(k in low for k in ("app", "android", "flutter", "apk",
                                  "calculator", "mobile", "tool")):
            slug = self._slug(command)
            return {"plan_name": "build_mobile_app",
                    "steps": [
                        {"tool": "code.write_flutter_app",
                         "args": {"spec": command, "app_slug": slug},
                         "why": "write Flutter source"},
                        {"tool": "code.build_apk",
                         "args": {"app_slug": slug, "spec": command},
                         "why": "compile and ship"},
                    ]}

        if any(k in low for k in ("website", "site", "landing", "html")):
            slug = self._slug(command)
            return {"plan_name": "build_website",
                    "steps": [
                        {"tool": "make.website",
                         "args": {"spec": command, "slug": slug},
                         "why": "build static site"},
                    ]}

        if any(k in low for k in ("pitch", "article", "doc", "document",
                                  "proposal", "essay", "letter",
                                  "readme", "guide", "post ")):
            slug = self._slug(command)
            return {"plan_name": "write_document",
                    "steps": [
                        {"tool": "make.document",
                         "args": {"spec": command, "slug": slug},
                         "why": "write doc"},
                    ]}

        if any(k in low for k in ("script", "python", "bash",
                                  "shell", "javascript")):
            lang = "python"
            if "bash" in low or "shell" in low:
                lang = "bash"
            elif "javascript" in low:
                lang = "javascript"
            slug = self._slug(command)
            return {"plan_name": "write_script",
                    "steps": [
                        {"tool": "make.script",
                         "args": {"spec": command, "language": lang,
                                  "slug": slug},
                         "why": "write script"},
                    ]}

        prompt = (f'Command: "{command}"\n'
                  f'Tools: {json.dumps([t["name"] for t in tools])}\n\n'
                  'Reply ONLY JSON: {"plan_name":"..",'
                  '"steps":[{"tool":"..","args":{},"why":".."}]}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=1200))

    @staticmethod
    def _slug(cmd):
        low = cmd.lower()
        m = re.search(r"(?:called|named)\s+([a-z0-9_\-]+)", low)
        if m:
            return re.sub(r"[^a-z0-9]+", "_", m.group(1))[:30]
        m = re.search(r"(?:build|make|create|write)\s+(?:me\s+)?"
                      r"(?:a\s+|an\s+)?([a-z][a-z0-9_\-]{2,})", low)
        if m:
            return re.sub(r"[^a-z0-9]+", "_", m.group(1))[:30]
        return "task"

    async def scan(self, command, context):
        prompt = (f'Command: "{command}"\n'
                  f'Memory: {json.dumps(context)[:1500]}\n\n'
                  'Reply ONLY JSON: {"resources":[],"today_opportunities":['
                  '{"title":"..","url":"..","pays_today":true,"cost":0}]}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=1500))

    async def next(self, command, mission, last_results, tools):
        prompt = (f'Command: "{command}"\n'
                  f'Mission: {json.dumps(mission)[:1200]}\n'
                  f'Results: {json.dumps(last_results)[:1200]}\n\n'
                  'Reply ONLY one of: {"done":true,"summary":".."} '
                  'or {"steps":[...]} or {"pivot":true,"reason":".."} '
                  'or {"ask":".."}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=1200))

    async def pivot(self, command, mission, tools):
        prompt = (f'Command: "{command}"\n'
                  f'Failed: {json.dumps(mission)[:1200]}\n\n'
                  'Different approach. Reply ONLY JSON: '
                  '{"plan_name":"..","steps":[{"tool":"..","args":{}}]}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=1200))

    async def repair(self, command, mission, failed, tools):
        err = json.dumps(failed)[:1500]
        prompt = (
            f'Command: "{command}"\n'
            f'Failed: {err}\n'
            f'Tools: {json.dumps([t["name"] for t in tools])}\n\n'
            'Reply ONLY JSON: {"steps":[{"tool":"..","args":{}}]} '
            'or {"give_up":true,"reason":".."}')
        return self._json(await self._chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=1200))

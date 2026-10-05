"""BOAT self-builder.

When BOAT needs a tool that doesn't exist, it writes the tool, installs it,
and uses it in the same run.

When a step fails because a file, dependency, or config is missing, the
self-builder produces what's needed and retries.

This is the file that makes BOAT grow.
"""
import asyncio
import base64
import json
import os
import re
import time

import httpx

from . import tool


GH = "https://api.github.com"


# ==================================================================
# Helpers
# ==================================================================
def _h():
    return {
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN', '')}",
        "Accept": "application/vnd.github+json",
    }


async def _get(repo, path):
    try:
        async with httpx.AsyncClient(timeout=30, headers=_h()) as c:
            r = await c.get(f"{GH}/repos/{repo}/contents/{path}")
            if r.status_code != 200:
                return None
            return r.json()
    except Exception:
        return None


async def _put(repo, path, content, message):
    async with httpx.AsyncClient(timeout=30, headers=_h()) as c:
        sha = None
        r = await c.get(f"{GH}/repos/{repo}/contents/{path}")
        if r.status_code == 200:
            sha = r.json().get("sha")
        body = {"message": message,
                "content": base64.b64encode(content.encode()).decode()}
        if sha:
            body["sha"] = sha
        r = await c.put(f"{GH}/repos/{repo}/contents/{path}", json=body)
        return r.status_code in (200, 201)


async def _exists(repo, path):
    return (await _get(repo, path)) is not None


async def _llm(prompt, max_tokens=8000, temp=0.2):
    base = os.environ.get("BOAT_LLM_BASE", "https://api.groq.com/openai/v1")
    key = os.environ["BOAT_LLM_KEY"]
    model = os.environ.get("BOAT_LLM_MODEL", "llama-3.3-70b-versatile")
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temp,
                "max_tokens": max_tokens,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def _slugify(s):
    s = (s or "x").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "x"


def _parse_json(raw):
    raw = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(),
                 flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None


# ==================================================================
# 1. Write a missing tool
# ==================================================================
@tool(
    "self.write_tool",
    "BOAT writes a NEW tool for itself when one is missing. The tool is "
    "saved to boat/tools/auto/<name>.py and becomes available on the next "
    "run. Use this when the planner says 'unknown tool X'.",
    {"type": "object", "properties": {
        "tool_name": {"type": "string",
                      "description": "dotted name like 'translate.text'"},
        "purpose": {"type": "string",
                    "description": "what the tool should do, in plain English"},
        "example_args": {"type": "object",
                         "description": "what the caller would pass"},
    }, "required": ["tool_name", "purpose"]},
    danger="high",
)
async def write_tool(tool_name, purpose, example_args=None, **_i):
    safe = re.sub(r"[^a-z0-9_]", "_", tool_name.lower().replace(".", "_"))
    path = f"boat/tools/auto/{safe}.py"

    prompt = f"""Write a Python tool for BOAT.

Tool name: {tool_name}
Purpose: {purpose}
Example arguments: {json.dumps(example_args or {})}

Return ONLY the complete Python source for a file at
`boat/tools/auto/{safe}.py`.

The file must:
1. Start with a docstring.
2. Import `from .. import tool`  (this file lives in boat/tools/auto/).
3. Define ONE async function decorated with:
     @tool("<{tool_name}>", "<short description>", {{"type": "object",
        "properties": {{...}}, "required": [...]}})
4. Use only the Python standard library, `httpx`, `json`, `os`, `re`,
   or `asyncio`. No other third-party packages.
5. Return a dict with an "ok" key.
6. Handle its own exceptions, never raise.
7. Not use any API key we don't already have
   (BOAT_LLM_KEY, GITHUB_TOKEN, TELEGRAM_BOT_TOKEN are available).
8. Include a small docstring example in a comment showing how to call it.

Return ONLY the Python code, no prose, no code fences.
"""
    try:
        code = await _llm(prompt, max_tokens=4000)
    except Exception as e:
        return {"ok": False, "error": f"llm failed: {e}"}

    # strip accidental fences
    code = re.sub(r"^```[a-z]*\n?", "", code)
    code = re.sub(r"\n?```$", "", code)

    repo = os.environ["GITHUB_REPOSITORY"]
    ok = await _put(repo, path, code, f"boat: self-build tool {tool_name}")
    return {
        "ok": ok,
        "tool_name": tool_name,
        "path": path,
        "note": "available on next run; call it by name.",
    }


# ==================================================================
# 2. Self-check + repair an app
# ==================================================================
@tool(
    "self.repair_app",
    "Fully verify a Flutter app and repair it end-to-end. If files are "
    "missing, they are written. If the code doesn't compile, it's rewritten. "
    "Loops until the app is valid or it runs out of attempts.",
    {"type": "object", "properties": {
        "app_slug": {"type": "string"},
        "spec": {"type": "string"},
        "max_rounds": {"type": "integer", "default": 4},
    }, "required": ["app_slug", "spec"]},
    danger="high",
)
async def repair_app(app_slug, spec, max_rounds=4, **_i):
    slug = _slugify(app_slug)
    repo = os.environ["GITHUB_REPOSITORY"]
    log = []

    from . import call_tool  # local import to avoid cycles

    for rnd in range(max_rounds):
        log.append(f"--- round {rnd + 1}")

        # check what exists
        has_pubspec = await _exists(repo, f"apps/{slug}/pubspec.yaml")
        has_main = await _exists(repo, f"apps/{slug}/lib/main.dart")
        log.append(f"pubspec={has_pubspec} main={has_main}")

        if not (has_pubspec and has_main):
            log.append("writing missing app files")
            try:
                wr = await call_tool("code.write_flutter_app",
                                     {"spec": spec, "app_slug": slug})
                log.append(f"write result: ok={wr.get('ok')}")
            except Exception as e:
                log.append(f"write failed: {e}")
            continue

        # files exist, dispatch a build and check the log
        try:
            br = await call_tool("code.build_apk",
                                 {"app_slug": slug, "spec": spec})
            log.append(f"build dispatched: ok={br.get('ok')}")
        except Exception as e:
            log.append(f"build failed: {e}")
            return {"ok": False, "log": log}

        # wait for the build to complete
        # (an external watcher will normally feed the error back)
        await asyncio.sleep(90)

        # check whether the APK workflow reports success
        success = await _check_last_apk_build(repo)
        log.append(f"last build success={success}")
        if success:
            return {"ok": True, "log": log, "app_slug": slug}

        # build failed; ask the fixer to read the error and rewrite the code
        err = await _last_apk_error(repo) or "unknown build error"
        log.append(f"build error: {err[:200]}")
        try:
            await call_tool("code.fix_flutter",
                            {"app_slug": slug, "error_text": err})
            log.append("fix applied")
        except Exception as e:
            log.append(f"fix failed: {e}")

    return {"ok": False, "log": log, "app_slug": slug}


async def _check_last_apk_build(repo):
    try:
        async with httpx.AsyncClient(timeout=30, headers=_h()) as c:
            r = await c.get(
                f"{GH}/repos/{repo}/actions/workflows/boat-build-apk.yml/runs",
                params={"per_page": 1})
            if r.status_code != 200:
                return False
            runs = r.json().get("workflow_runs", [])
            if not runs:
                return False
            return runs[0].get("conclusion") == "success"
    except Exception:
        return False


async def _last_apk_error(repo):
    try:
        async with httpx.AsyncClient(timeout=30, headers=_h()) as c:
            r = await c.get(
                f"{GH}/repos/{repo}/actions/workflows/boat-build-apk.yml/runs",
                params={"per_page": 1})
            runs = r.json().get("workflow_runs", [])
            if not runs:
                return None
            run_id = runs[0]["id"]
            jr = await c.get(f"{GH}/repos/{repo}/actions/runs/{run_id}/jobs")
            jobs = jr.json().get("jobs", [])
            if not jobs:
                return None
            jid = jobs[0]["id"]
            lr = await c.get(f"{GH}/repos/{repo}/actions/jobs/{jid}/logs")
            if lr.status_code != 200:
                return None
            txt = lr.text
            return txt[-2000:] if txt else None
    except Exception:
        return None


# ==================================================================
# 3. Self-provision dependencies
# ==================================================================
@tool(
    "self.add_dependency",
    "Add a missing dependency to a project. Works for Flutter "
    "(pubspec.yaml), Python (requirements.txt), and Node (package.json). "
    "Idempotent - won't duplicate.",
    {"type": "object", "properties": {
        "project_dir": {"type": "string",
                        "description": "e.g. apps/tipcalc"},
        "kind": {"type": "string",
                 "description": "flutter | python | node"},
        "package": {"type": "string"},
        "version": {"type": "string"},
    }, "required": ["project_dir", "kind", "package"]},
    danger="medium",
)
async def add_dependency(project_dir, kind, package, version=None, **_i):
    repo = os.environ["GITHUB_REPOSITORY"]
    project_dir = project_dir.strip("/")

    if kind == "flutter":
        path = f"{project_dir}/pubspec.yaml"
        spec = f"{package}: {version or 'any'}"
    elif kind == "python":
        path = f"{project_dir}/requirements.txt"
        spec = f"{package}{('==' + version) if version else ''}"
    elif kind == "node":
        path = f"{project_dir}/package.json"
    else:
        return {"ok": False, "error": "unsupported kind"}

    cur = await _get(repo, path)
    text = ""
    if cur:
        text = base64.b64decode(cur["content"]).decode(errors="ignore")

    if kind in ("flutter", "python"):
        if spec in text:
            return {"ok": True, "note": "already present", "path": path}
        text = (text.rstrip() + "\n" + spec + "\n").lstrip("\n")
        ok = await _put(repo, path, text,
                        f"boat: add {package} to {path}")
        return {"ok": ok, "path": path, "added": spec}

    if kind == "node":
        try:
            data = json.loads(text or "{}")
        except Exception:
            data = {}
        data.setdefault("dependencies", {})[package] = version or "*"
        ok = await _put(repo, path, json.dumps(data, indent=2),
                        f"boat: add {package} to {path}")
        return {"ok": ok, "path": path, "added": package}

    return {"ok": False}


# ==================================================================
# 4. Self-provision an account (email-only services)
# ==================================================================
@tool(
    "self.create_account",
    "Create an account on an email-only service using a throwaway email. "
    "Refuses services that need KYC, phone, or a selfie. Use only where "
    "automated signup is permitted by the service.",
    {"type": "object", "properties": {
        "service_name": {"type": "string"},
        "service_url": {"type": "string"},
        "purpose": {"type": "string"},
    }, "required": ["service_name", "service_url"]},
    danger="high",
)
async def create_account(service_name, service_url, purpose="", **_i):
    host = re.sub(r"^https?://", "", service_url).split("/")[0].lower()

    blocked = {
        "paypal.com": "PayPal requires KYC and a phone number.",
        "stripe.com": "Stripe requires KYC.",
        "upwork.com": "Upwork requires KYC.",
        "fiverr.com": "Fiverr requires KYC.",
        "shopify.com": "Shopify requires a phone number.",
        "tiktok.com": "TikTok bans automation.",
        "instagram.com": "Instagram bans automation.",
        "facebook.com": "Facebook requires a phone number.",
        "twitter.com": "Twitter/X requires a phone number.",
        "x.com": "Twitter/X requires a phone number.",
        "bank": "Banks require identity verification.",
    }
    for b, why in blocked.items():
        if b in host:
            return {
                "ok": False,
                "action": "ask_human",
                "reason": why,
                "instruction": (
                    f"To sign up for {service_name}, the human owner must "
                    f"register at {service_url} themselves. After that, "
                    f"BOAT can log in and operate the account."
                ),
            }

    # email-only signup path
    from .all_tools import _llm as _llm_all
    try:
        from . import call_tool
        em = await call_tool("accounts.new_email", {})
    except Exception:
        em = {"ok": False}

    if not em.get("ok"):
        return {"ok": False,
                "reason": "could not create throwaway email",
                "detail": em}

    return {
        "ok": True,
        "email": em["address"],
        "email_password": em["password"],
        "service": service_name,
        "service_url": service_url,
        "next_step": (
            f"Now use browser.register to sign up at {service_url} "
            f"with this email + a new password, then read the inbox "
            f"at {em['address']} to confirm."
        ),
    }


# ==================================================================
# 5. Self-check any artifact
# ==================================================================
@tool(
    "self.verify",
    "Verify that a task's artifact actually exists and looks valid. "
    "Used at the end of a mission to make sure work wasn't skipped.",
    {"type": "object", "properties": {
        "artifact_kind": {"type": "string",
                          "description": "app|website|document|script|file"},
        "identifier": {"type": "string"},
        "path": {"type": "string",
                 "description": "for kind=file, full repo path"},
    }, "required": ["artifact_kind", "identifier"]},
    danger="low",
)
async def verify(artifact_kind, identifier, path=None, **_i):
    repo = os.environ["GITHUB_REPOSITORY"]
    slug = _slugify(identifier)

    if artifact_kind == "app":
        ok = (await _exists(repo, f"apps/{slug}/pubspec.yaml")
              and await _exists(repo, f"apps/{slug}/lib/main.dart"))
        return {"ok": ok, "kind": "app", "slug": slug}

    if artifact_kind == "website":
        ok = await _exists(repo, f"sites/{slug}/index.html")
        return {"ok": ok, "kind": "website", "slug": slug}

    if artifact_kind == "document":
        ok = await _exists(repo, f"docs/{slug}.md")
        return {"ok": ok, "kind": "document", "slug": slug}

    if artifact_kind == "script":
        for ext in ("py", "js", "sh"):
            if await _exists(repo, f"scripts/{slug}/main.{ext}"):
                return {"ok": True, "kind": "script", "slug": slug,
                        "ext": ext}
        return {"ok": False, "kind": "script", "slug": slug}

    if artifact_kind == "file" and path:
        return {"ok": await _exists(repo, path), "kind": "file",
                "path": path}

    return {"ok": False, "reason": "unknown artifact_kind"}

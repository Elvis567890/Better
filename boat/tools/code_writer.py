"""Turn a plain-English spec into a full Flutter app and dispatch the APK build.

Parameter names are tolerant: the LLM may send 'project_name', 'name',
'app', 'slug', etc. All of these map to the same thing.
"""
import json, os, re
import httpx
from . import tool


async def _llm(prompt, max_tokens=8000):
    base = os.environ.get("BOAT_LLM_BASE", "https://api.groq.com/openai/v1")
    key = os.environ["BOAT_LLM_KEY"]
    model = os.environ.get("BOAT_LLM_MODEL", "llama-3.3-70b-versatile")
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(f"{base}/chat/completions",
                         headers={"Authorization": f"Bearer {key}"},
                         json={"model": model,
                               "messages": [{"role": "user", "content": prompt}],
                               "temperature": 0.2, "max_tokens": max_tokens})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def _pick(*candidates, default=None):
    """Return the first non-empty value."""
    for c in candidates:
        if c:
            return c
    return default


def _slugify(s):
    s = (s or "app").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s or "app"


@tool(
    "code.write_flutter_app",
    "Given a plain-English spec, write a COMPLETE Flutter app (source files) "
    "and push it into the repo at apps/<slug>/ so the build workflow can compile it. "
    "Accepts app_slug OR project_name OR name as the identifier.",
    {"type": "object", "properties": {
        "spec": {"type": "string", "description": "what the app should do"},
        "app_slug": {"type": "string", "description": "short id, e.g. tipcalc"},
        "project_name": {"type": "string", "description": "alias for app_slug"},
        "name": {"type": "string", "description": "alias for app_slug"},
        "app_name": {"type": "string", "description": "display name"},
        "package_name": {"type": "string"},
    }, "required": ["spec"]},
    danger="high",
)
async def write_flutter_app(spec, app_slug=None, project_name=None,
                            name=None, app_name=None, package_name=None,
                            **_ignored):
    # Tolerate whatever the LLM calls the identifier
    slug_source = _pick(app_slug, project_name, name, app_name, "app")
    app_slug = _slugify(slug_source)
    app_name = _pick(app_name, project_name, name,
                     app_slug.replace("_", " ").title().replace(" ", ""))
    package_name = _pick(package_name, f"com.boat.{app_slug}")

    prompt = f"""You are a senior Flutter engineer.
Write a COMPLETE, COMPILABLE Flutter app for this spec:

--- SPEC ---
{spec}
--- END SPEC ---

App name: {app_name}
Package name: {package_name}

Return ONLY a JSON object, no prose, no code fences:

{{
  "files": {{
    "pubspec.yaml": "...",
    "lib/main.dart": "..."
  }}
}}

Rules:
- Only well-known public packages that exist on pub.dev.
- Prefer stable versions (no beta/dev).
- No TODOs. Every screen complete.
- main.dart must be self-contained.
- Use Material 3.
"""
    try:
        raw = await _llm(prompt, max_tokens=8000)
    except Exception as e:
        return {"ok": False, "error": f"llm call failed: {e}"}

    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(),
                 flags=re.MULTILINE).strip()
    try:
        data = json.loads(raw)
    except Exception as e:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return {"ok": False, "error": f"model returned non-JSON: {e}",
                    "head": raw[:400]}
        try:
            data = json.loads(m.group(0))
        except Exception as e2:
            return {"ok": False, "error": f"json parse failed: {e2}",
                    "head": raw[:400]}

    files = data.get("files") or {}
    if not files:
        return {"ok": False, "error": "no files returned",
                "keys": list(data.keys())}

    repo = os.environ["GITHUB_REPOSITORY"]
    from .github_tool import github_push_file
    pushed = []
    for rel, content in files.items():
        path = f"apps/{app_slug}/{rel}"
        try:
            r = await github_push_file(repo=repo, path=path,
                                       content=content,
                                       message=f"boat: write {app_slug}/{rel}")
            pushed.append({"path": path, "ok": r.get("ok")})
        except Exception as e:
            pushed.append({"path": path, "ok": False, "error": str(e)})

    return {
        "ok": True,
        "app_slug": app_slug,
        "app_name": app_name,
        "package_name": package_name,
        "files_written": len(pushed),
        "paths": [p["path"] for p in pushed],
    }


@tool(
    "code.build_apk",
    "Dispatch the APK build workflow for an app already written to the repo. "
    "Accepts app_slug OR project_name OR name as the identifier.",
    {"type": "object", "properties": {
        "app_slug": {"type": "string"},
        "project_name": {"type": "string", "description": "alias for app_slug"},
        "name": {"type": "string", "description": "alias for app_slug"},
        "app_name": {"type": "string"},
        "package_name": {"type": "string"},
        "chat_id": {"type": "string"},
    }, "required": []},
)
async def build_apk(app_slug=None, project_name=None, name=None,
                    app_name=None, package_name=None,
                    chat_id=None, **_ignored):
    from .github_tool import github_dispatch

    slug_source = _pick(app_slug, project_name, name, app_name, "app")
    app_slug = _slugify(slug_source)
    app_name = _pick(app_name, project_name, name,
                     app_slug.replace("_", " ").title().replace(" ", ""))
    package_name = _pick(package_name, f"com.boat.{app_slug}")

    # chat_id: fall back to TELEGRAM_ALLOWED
    chat_id = _pick(chat_id, os.environ.get("TELEGRAM_ALLOWED", ""))

    repo = os.environ["GITHUB_REPOSITORY"]
    return await github_dispatch(
        repo=repo,
        workflow="boat-build-apk.yml",
        inputs={
            "app_dir": f"apps/{app_slug}",
            "app_name": app_name,
            "package_name": package_name,
            "chat_id": str(chat_id) if chat_id else "",
        },
        )

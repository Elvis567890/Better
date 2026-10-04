"""Turn a plain-English spec into a full Flutter app and dispatch the APK build."""
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


@tool(
    "code.write_flutter_app",
    "Given a plain-English spec, write a COMPLETE Flutter app (source files) "
    "and push it into the repo at apps/<slug>/ so the build workflow can compile it.",
    {"type": "object", "properties": {
        "spec": {"type": "string"},
        "app_slug": {"type": "string"},
        "app_name": {"type": "string"},
        "package_name": {"type": "string"},
    }, "required": ["spec", "app_slug"]},
    danger="high",
)
async def write_flutter_app(spec, app_slug, app_name=None, package_name=None):
    app_name = app_name or app_slug.replace("_", " ").title().replace(" ", "")
    package_name = package_name or f"com.boat.{app_slug}"

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
    raw = await _llm(prompt, max_tokens=8000)
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(raw)
    except Exception as e:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return {"ok": False, "error": f"model returned non-JSON: {e}", "head": raw[:400]}
        data = json.loads(m.group(0))

    files = data.get("files") or {}
    if not files:
        return {"ok": False, "error": "no files returned", "keys": list(data.keys())}

    repo = os.environ["GITHUB_REPOSITORY"]
    from .github_tool import github_push_file
    pushed = []
    for rel, content in files.items():
        path = f"apps/{app_slug}/{rel}"
        r = await github_push_file(repo=repo, path=path, content=content,
                                   message=f"boat: write {app_slug}/{rel}")
        pushed.append({"path": path, "ok": r.get("ok")})

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
    "Dispatch the APK build workflow for an app already written to the repo.",
    {"type": "object", "properties": {
        "app_slug": {"type": "string"},
        "app_name": {"type": "string"},
        "package_name": {"type": "string"},
        "chat_id": {"type": "string"},
    }, "required": ["app_slug", "chat_id"]},
)
async def build_apk(app_slug, chat_id, app_name=None, package_name=None):
    from .github_tool import github_dispatch
    repo = os.environ["GITHUB_REPOSITORY"]
    return await github_dispatch(
        repo=repo,
        workflow="boat-build-apk.yml",
        inputs={
            "app_dir": f"apps/{app_slug}",
            "app_name": app_name or app_slug,
            "package_name": package_name or f"com.boat.{app_slug}",
            "chat_id": str(chat_id),
        },
    )

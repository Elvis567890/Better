"""Flutter app writer + APK builder with self-healing.

Self-healing behaviour:
  - build_apk checks the app folder exists on GitHub before dispatching.
  - If it's missing and a spec was given, it calls write_flutter_app first.
  - write_flutter_app re-verifies the files actually landed on GitHub.
  - Every failure returns a "next_action" hint so the brain's repair loop
    knows exactly what to do without guessing.
"""
import json
import os
import re

import httpx

from . import tool

GH_API = "https://api.github.com"


def _gh_headers():
    return {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }


async def _gh_exists(repo, path):
    """True if the file/dir exists on the default branch."""
    try:
        async with httpx.AsyncClient(timeout=20, headers=_gh_headers()) as c:
            r = await c.get(f"{GH_API}/repos/{repo}/contents/{path}")
            return r.status_code == 200
    except Exception:
        return False


async def _llm(prompt, max_tokens=8000):
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
                "temperature": 0.2,
                "max_tokens": max_tokens,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def _pick(*vals, default=None):
    for v in vals:
        if v:
            return v
    return default


def _slugify(s):
    s = (s or "app").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "app"


def _parse_files(raw):
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


# ---------------------------------------------------------------- write
@tool(
    "code.write_flutter_app",
    "Write a complete Flutter app and push its source files to the repo at "
    "apps/<slug>/. Call this BEFORE code.build_apk.",
    {"type": "object", "properties": {
        "spec": {"type": "string", "description": "plain-English app description"},
        "app_slug": {"type": "string", "description": "folder name, e.g. tipcalc"},
        "project_name": {"type": "string", "description": "alias for app_slug"},
        "name": {"type": "string", "description": "alias for app_slug"},
        "app_name": {"type": "string", "description": "display name, e.g. TipCalc"},
        "package_name": {"type": "string", "description": "com.example.app"},
    }, "required": ["spec"]},
    danger="high",
)
async def write_flutter_app(spec, app_slug=None, project_name=None,
                            name=None, app_name=None, package_name=None,
                            **_ignored):
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
- Only well-known packages that exist on pub.dev.
- Prefer stable versions, no beta/dev.
- No TODOs. Every screen complete.
- main.dart must be self-contained and compile.
- Use Material 3.
"""
    try:
        raw = await _llm(prompt, max_tokens=8000)
    except Exception as e:
        return {"ok": False, "error": f"llm failed: {e}",
                "next_action": "retry with a simpler spec"}

    data = _parse_files(raw)
    if not data or not isinstance(data.get("files"), dict):
        return {"ok": False, "error": "llm did not return a files object",
                "head": (raw or "")[:400],
                "next_action": "retry code.write_flutter_app"}

    repo = os.environ["GITHUB_REPOSITORY"]
    from .github_tool import github_push_file
    pushed = []
    for rel, content in data["files"].items():
        path = f"apps/{app_slug}/{rel}"
        try:
            r = await github_push_file(repo=repo, path=path,
                                       content=content,
                                       message=f"boat: write {path}")
            pushed.append({"path": path, "ok": r.get("ok")})
        except Exception as e:
            pushed.append({"path": path, "ok": False, "error": str(e)})

    ok_count = sum(1 for p in pushed if p.get("ok"))
    pubspec_ok = await _gh_exists(repo, f"apps/{app_slug}/pubspec.yaml")
    main_ok = await _gh_exists(repo, f"apps/{app_slug}/lib/main.dart")

    if not (pubspec_ok and main_ok):
        return {
            "ok": False,
            "error": "files pushed but not confirmed on GitHub",
            "pushed": pushed,
            "pubspec_present": pubspec_ok,
            "main_present": main_ok,
            "next_action": "retry code.write_flutter_app",
        }

    return {
        "ok": True,
        "app_slug": app_slug,
        "app_name": app_name,
        "package_name": package_name,
        "files_written": ok_count,
        "paths": [p["path"] for p in pushed],
        "next_action": "now call code.build_apk with the same app_slug",
    }


# ---------------------------------------------------------------- build
@tool(
    "code.build_apk",
    "Dispatch the APK build for an app already in the repo. "
    "Self-healing: if the app folder doesn't exist yet and a spec is given, "
    "it writes the app first, then dispatches the build.",
    {"type": "object", "properties": {
        "app_slug": {"type": "string"},
        "project_name": {"type": "string", "description": "alias for app_slug"},
        "name": {"type": "string", "description": "alias for app_slug"},
        "app_name": {"type": "string"},
        "package_name": {"type": "string"},
        "chat_id": {"type": "string"},
        "spec": {"type": "string",
                 "description": "plain-English spec; used to auto-write "
                                "if the app folder is missing"},
    }, "required": []},
    danger="high",
)
async def build_apk(app_slug=None, project_name=None, name=None,
                    app_name=None, package_name=None,
                    chat_id=None, spec=None, **_ignored):
    from .github_tool import github_dispatch

    slug_source = _pick(app_slug, project_name, name, app_name, "app")
    app_slug = _slugify(slug_source)
    app_name = _pick(app_name, project_name, name,
                     app_slug.replace("_", " ").title().replace(" ", ""))
    package_name = _pick(package_name, f"com.boat.{app_slug}")
    chat_id = _pick(chat_id, os.environ.get("TELEGRAM_ALLOWED", ""))
    repo = os.environ["GITHUB_REPOSITORY"]

    # ---- SELF-HEAL: does the app actually exist? ----
    exists = await _gh_exists(repo, f"apps/{app_slug}/pubspec.yaml")

    if not exists:
        if spec:
            # auto-write the app first, then continue
            wr = await write_flutter_app(spec=spec, app_slug=app_slug,
                                         app_name=app_name,
                                         package_name=package_name)
            if not wr.get("ok"):
                return {
                    "ok": False,
                    "error": "auto-write of app failed",
                    "detail": wr,
                    "next_action": "retry code.write_flutter_app with a simpler spec",
                }
        else:
            return {
                "ok": False,
                "error": f"apps/{app_slug}/pubspec.yaml not found, and no "
                         f"spec was provided to create it",
                "next_action": (
                    "call code.write_flutter_app with spec=<the app spec>, "
                    "app_slug={app_slug}, then call code.build_apk again"
                ).format(app_slug=app_slug),
            }

    dispatch = await github_dispatch(
        repo=repo,
        workflow="boat-build-apk.yml",
        inputs={
            "app_dir": f"apps/{app_slug}",
            "app_name": app_name,
            "package_name": package_name,
            "chat_id": str(chat_id) if chat_id else "",
        },
    )

    return {
        "ok": dispatch.get("ok", False),
        "app_slug": app_slug,
        "dispatched": dispatch,
        "note": "APK build running; check Telegram in a few minutes",
    }

"""Generic maker: websites, documents, scripts, anything text-based.

One tool family that lets BOAT produce and deliver many kinds of artifacts:
  - make.website    -> HTML/CSS/JS site, published via GitHub Pages
  - make.document   -> markdown doc, article, pitch, README, guide
  - make.script     -> any code file (python, js, bash, etc.)
  - make.any        -> escape hatch: LLM writes, we push wherever asked

All push to GitHub. Websites are served by GitHub Pages automatically
(once enabled in repo settings). Documents and scripts live in the repo.
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
                               "temperature": 0.2,
                               "max_tokens": max_tokens})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def _slugify(s):
    s = (s or "item").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "item"


def _parse_files_json(raw):
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


async def _push_files(repo, base_dir, files):
    from .github_tool import github_push_file
    pushed = []
    for rel, content in files.items():
        path = f"{base_dir}/{rel}"
        try:
            r = await github_push_file(repo=repo, path=path,
                                       content=content,
                                       message=f"boat: write {path}")
            pushed.append({"path": path, "ok": r.get("ok")})
        except Exception as e:
            pushed.append({"path": path, "ok": False, "error": str(e)})
    return pushed


# ---------------------------------------------------------------- website
@tool(
    "make.website",
    "Build a complete website (HTML + CSS + JS) from a plain-English spec "
    "and push it to the repo at sites/<slug>/. Once GitHub Pages is enabled, "
    "the site is live at https://<owner>.github.io/<repo>/<slug>/",
    {"type": "object", "properties": {
        "spec": {"type": "string"},
        "slug": {"type": "string"},
        "project_name": {"type": "string", "description": "alias for slug"},
        "name": {"type": "string", "description": "alias for slug"},
    }, "required": ["spec"]},
    danger="high",
)
async def make_website(spec, slug=None, project_name=None, name=None,
                       **_ignored):
    slug = _slugify(slug or project_name or name or "site")

    prompt = f"""You are a senior web developer.
Build a COMPLETE, working website for this spec:

--- SPEC ---
{spec}
--- END SPEC ---

Return ONLY a JSON object, no prose, no code fences:

{{
  "files": {{
    "index.html": "...full HTML...",
    "style.css": "...CSS...",
    "script.js": "...JS... (if needed)"
  }}
}}

Rules:
- Plain HTML/CSS/JS. No build step. No external frameworks.
- Mobile-responsive. Looks good on a phone.
- Self-contained. No external asset URLs unless from a public CDN.
- No placeholders like "TODO" or "lorem ipsum" unless the spec asks for it.
- If the spec mentions images and none are provided, use CSS gradients or
  SVG placeholders, not broken image tags.
"""
    try:
        raw = await _llm(prompt, max_tokens=8000)
    except Exception as e:
        return {"ok": False, "error": f"llm failed: {e}"}

    data = _parse_files_json(raw)
    if not data or not isinstance(data.get("files"), dict):
        return {"ok": False, "error": "no files",
                "head": (raw or "")[:400]}

    repo = os.environ["GITHUB_REPOSITORY"]
    owner, reponame = repo.split("/", 1)
    pushed = await _push_files(repo, f"sites/{slug}", data["files"])

    pages_url = f"https://{owner.lower()}.github.io/{reponame}/{slug}/"
    return {
        "ok": True,
        "slug": slug,
        "files_written": len(pushed),
        "paths": [p["path"] for p in pushed],
        "live_url_when_pages_enabled": pages_url,
    }


# ------------------------------------------------------------- document
@tool(
    "make.document",
    "Write a document (article, pitch, proposal, README, guide, letter) "
    "and push it to the repo at docs/<slug>.md",
    {"type": "object", "properties": {
        "spec": {"type": "string", "description": "what the doc should say / be for"},
        "slug": {"type": "string"},
        "title": {"type": "string"},
        "project_name": {"type": "string", "description": "alias for slug"},
        "name": {"type": "string", "description": "alias for slug"},
    }, "required": ["spec"]},
    danger="medium",
)
async def make_document(spec, slug=None, title=None,
                        project_name=None, name=None, **_ignored):
    slug = _slugify(slug or project_name or name or "doc")
    title = title or slug.replace("_", " ").title()

    prompt = f"""You are a professional writer.
Write a complete, high-quality document.

Title: {title}
Spec: {spec}

Return ONLY the document as plain Markdown. No code fences. No preamble.
Start with "# {title}".
"""
    try:
        body = await _llm(prompt, max_tokens=6000)
    except Exception as e:
        return {"ok": False, "error": f"llm failed: {e}"}

    repo = os.environ["GITHUB_REPOSITORY"]
    from .github_tool import github_push_file
    path = f"docs/{slug}.md"
    r = await github_push_file(repo=repo, path=path, content=body,
                               message=f"boat: write {path}")
    return {
        "ok": r.get("ok", False),
        "slug": slug,
        "path": path,
        "chars": len(body),
    }


# --------------------------------------------------------------- script
@tool(
    "make.script",
    "Write a script (Python, JavaScript, Bash, etc.) and push it to the repo "
    "at scripts/<slug>/<filename>",
    {"type": "object", "properties": {
        "spec": {"type": "string"},
        "language": {"type": "string", "description": "python, javascript, bash"},
        "slug": {"type": "string"},
        "project_name": {"type": "string", "description": "alias for slug"},
        "name": {"type": "string", "description": "alias for slug"},
    }, "required": ["spec", "language"]},
    danger="high",
)
async def make_script(spec, language, slug=None,
                      project_name=None, name=None, **_ignored):
    slug = _slugify(slug or project_name or name or "script")
    lang = (language or "python").lower()
    ext = {"python": "py", "py": "py",
           "javascript": "js", "js": "js",
           "bash": "sh", "sh": "sh"}.get(lang, "txt")

    prompt = f"""Write a COMPLETE, WORKING {lang} script.

Spec: {spec}

Return ONLY the raw code. No prose. No code fences. No explanation.
Every import must exist. Every function complete.
"""
    try:
        code = await _llm(prompt, max_tokens=6000)
    except Exception as e:
        return {"ok": False, "error": f"llm failed: {e}"}

    # strip accidental code fences
    code = re.sub(r"^```[a-z]*\n?", "", code)
    code = re.sub(r"\n?```$", "", code)

    repo = os.environ["GITHUB_REPOSITORY"]
    from .github_tool import github_push_file
    filename = f"main.{ext}"
    path = f"scripts/{slug}/{filename}"
    r = await github_push_file(repo=repo, path=path, content=code,
                               message=f"boat: write {path}")
    return {
        "ok": r.get("ok", False),
        "slug": slug,
        "path": path,
        "language": lang,
        "lines": code.count("\n") + 1,
    }


# ------------------------------------------------------------ escape hatch
@tool(
    "make.any",
    "Escape hatch: LLM writes arbitrary files and pushes them to the repo. "
    "Use when none of the specific makers fit. You describe the shape, "
    "the LLM fills the content.",
    {"type": "object", "properties": {
        "spec": {"type": "string", "description": "what to produce"},
        "target_dir": {"type": "string", "description": "e.g. mysite/ or tools/foo/"},
        "extra_hint": {"type": "string", "description": "e.g. 'React SPA' or 'just one file'"},
    }, "required": ["spec", "target_dir"]},
    danger="high",
)
async def make_any(spec, target_dir, extra_hint="", **_ignored):
    target_dir = target_dir.strip("/").replace(" ", "_")

    prompt = f"""Produce the files for this task.

Spec: {spec}
Hint: {extra_hint}

Return ONLY a JSON object, no prose, no code fences:

{{
  "files": {{
    "<relative path>": "<file contents>",
    ...
  }}
}}

Rules:
- Relative paths only, no leading slashes, no "..".
- Complete, working files. No placeholders.
- Choose sensible filenames and structure for the task.
"""
    try:
        raw = await _llm(prompt, max_tokens=8000)
    except Exception as e:
        return {"ok": False, "error": f"llm failed: {e}"}

    data = _parse_files_json(raw)
    if not data or not isinstance(data.get("files"), dict):
        return {"ok": False, "error": "no files", "head": (raw or "")[:400]}

    repo = os.environ["GITHUB_REPOSITORY"]
    pushed = await _push_files(repo, target_dir, data["files"])
    return {"ok": True, "dir": target_dir, "files_written": len(pushed),
            "paths": [p["path"] for p in pushed]}

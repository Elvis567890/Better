"""GitHub tools."""
import base64
import os
import httpx
from . import tool

API = "https://api.github.com"


def _h():
    return {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json"}


@tool("github.push_file", "Create or update a file in a GitHub repo.",
      {"type": "object", "properties": {
          "repo": {"type": "string"}, "path": {"type": "string"},
          "content": {"type": "string"},
          "message": {"type": "string", "default": "boat: update"},
          "branch": {"type": "string", "default": "main"}},
       "required": ["repo", "path", "content"]})
async def github_push_file(repo, path, content,
                           message="boat: update", branch="main"):
    async with httpx.AsyncClient(timeout=30, headers=_h()) as c:
        sha = None
        r = await c.get(f"{API}/repos/{repo}/contents/{path}",
                        params={"ref": branch})
        if r.status_code == 200:
            sha = r.json().get("sha")
        body = {"message": message, "branch": branch,
                "content": base64.b64encode(content.encode()).decode()}
        if sha:
            body["sha"] = sha
        r = await c.put(f"{API}/repos/{repo}/contents/{path}", json=body)
        return {"ok": r.status_code in (200, 201),
                "status": r.status_code, "body": r.text[:800]}


@tool("github.dispatch", "Trigger a GitHub Actions workflow.",
      {"type": "object", "properties": {
          "repo": {"type": "string"}, "workflow": {"type": "string"},
          "ref": {"type": "string", "default": "main"},
          "inputs": {"type": "object"}},
       "required": ["repo", "workflow"]})
async def github_dispatch(repo, workflow, ref="main", inputs=None):
    async with httpx.AsyncClient(timeout=30, headers=_h()) as c:
        r = await c.post(
            f"{API}/repos/{repo}/actions/workflows/{workflow}/dispatches",
            json={"ref": ref, "inputs": inputs or {}})
        return {"ok": r.status_code == 204, "status": r.status_code}

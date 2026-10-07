"""Self-builder."""
import json
import os
import re
import httpx
from . import tool


async def _llm(prompt, max_tokens=6000):
    base = os.environ.get("BOAT_LLM_BASE", "https://api.groq.com/openai/v1")
    key = os.environ["BOAT_LLM_KEY"]
    model = os.environ.get("BOAT_LLM_MODEL", "llama-3.3-70b-versatile")
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model,
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.2, "max_tokens": max_tokens})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


@tool("self.write_tool", "BOAT writes a new tool for itself.",
      {"type": "object", "properties": {
          "tool_name": {"type": "string"},
          "purpose": {"type": "string"},
          "example_args": {"type": "object"}},
       "required": ["tool_name", "purpose"]}, danger="high")
async def write_tool(tool_name, purpose, example_args=None, **_i):
    safe = re.sub(r"[^a-z0-9_]", "_", tool_name.lower().replace(".", "_"))
    path = f"boat/tools/auto/{safe}.py"
    code = await _llm(
        f"Write a Python tool for BOAT.\n"
        f"Tool name: {tool_name}\nPurpose: {purpose}\n\n"
        f"Return ONLY Python code for boat/tools/auto/{safe}.py. "
        f"Import from .. import tool. Return dict with 'ok' key.", 4000)
    code = re.sub(r"^```[a-z]*\n?", "", code)
    code = re.sub(r"\n?```$", "", code)
    from .github_tool import github_push_file
    repo = os.environ["GITHUB_REPOSITORY"]
    r = await github_push_file(repo=repo, path=path, content=code,
                               message=f"boat: self-build {tool_name}")
    return {"ok": r.get("ok"), "tool_name": tool_name, "path": path}

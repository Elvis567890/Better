"""Universal self-healer. Reads the actual error and does the right thing.

Categories handled:
  - unknown tool        -> write the tool
  - import error        -> rewrite the tool file
  - missing file        -> call the appropriate writer
  - rate limit (429)    -> sleep and retry
  - bad parameter       -> retry with mapped names
  - compile error       -> code.fix_flutter
  - no plan             -> fall back to a hardcoded plan
"""
import asyncio
import json
import os
import re
import time

from . import tool, REGISTRY, call_tool


def _classify(err: str):
    e = (err or "").lower()
    if "unknown tool" in e or "keyerror" in e and "tool" in e:
        return "unknown_tool"
    if "modulenotfound" in e or "importerror" in e:
        return "import_error"
    if "429" in e or "rate limit" in e or "busy" in e:
        return "rate_limit"
    if "no such file" in e or "not found" in e or "404" in e:
        return "missing_file"
    if "unexpected keyword argument" in e or "missing" in e and "argument" in e:
        return "bad_params"
    if "compile" in e or "failed" in e or "error" in e:
        return "compile_error"
    return "unknown"


def _extract_missing_tool(err: str):
    m = re.search(r"unknown tool:\s*([a-z0-9_.]+)", err or "", re.I)
    return m.group(1) if m else None


@tool(
    "self.auto_heal",
    "Universal self-healer. Give it the failed step and the error text. "
    "It diagnoses the failure and returns the correct next steps. "
    "This is called automatically by the brain when a step fails.",
    {"type": "object", "properties": {
        "failed_step": {"type": "object"},
        "error": {"type": "string"},
        "mission_context": {"type": "object"},
    }, "required": ["failed_step", "error"]},
    danger="medium",
)
async def auto_heal(failed_step, error, mission_context=None, **_i):
    kind = _classify(error)
    tool_name = (failed_step or {}).get("tool", "")
    args = (failed_step or {}).get("args", {})

    # ---- unknown tool: write it ----
    if kind == "unknown_tool":
        missing = _extract_missing_tool(error) or tool_name
        # if we don't know what it should do, ask the LLM to design it
        purpose = (
            f"A tool called {missing}. It was called with args "
            f"{json.dumps(args)} during mission "
            f"{json.dumps(mission_context or {})[:300]}. "
            f"It should do whatever those args imply."
        )
        try:
            await call_tool("self.write_tool", {
                "tool_name": missing,
                "purpose": purpose,
                "example_args": args,
            })
            return {
                "healed": True,
                "kind": "unknown_tool",
                "action": "wrote_tool",
                "note": f"tool {missing} will be available next run",
                "next_steps": [],
                "retry": False,
            }
        except Exception as e:
            return {"healed": False, "kind": kind, "error": str(e)}

    # ---- import error: rewrite the module ----
    if kind == "import_error":
        m = re.search(r"boat\.tools\.([a-z0-9_]+)", error or "")
        bad_module = m.group(1) if m else None
        if bad_module:
            try:
                await call_tool("self.write_tool", {
                    "tool_name": f"fix_{bad_module}",
                    "purpose": f"Rewrite {bad_module}.py to fix an import error.",
                    "example_args": {},
                })
                return {"healed": True, "kind": "import_error",
                        "action": "rewrote_module",
                        "note": f"{bad_module} will be fixed next run"}
            except Exception as e:
                return {"healed": False, "kind": kind, "error": str(e)}
        return {"healed": False, "kind": kind}

    # ---- rate limit: retry after a wait ----
    if kind == "rate_limit":
        await asyncio.sleep(15)
        return {
            "healed": True,
            "kind": "rate_limit",
            "action": "retry_same",
            "retry": True,
            "next_steps": [{"tool": tool_name, "args": args,
                            "why": "retry after rate limit"}],
        }

    # ---- missing file: call the writer ----
    if kind == "missing_file":
        t = (tool_name or "").lower()
        if "build" in t or "apk" in t:
            return {
                "healed": True, "kind": "missing_file",
                "action": "write_then_build",
                "next_steps": [
                    {"tool": "code.write_flutter_app",
                     "args": {"spec": (mission_context or {}).get(
                         "command", "build the app"),
                         "app_slug": args.get("app_slug",
                                              args.get("project_name",
                                                       "app"))},
                     "why": "write the app first"},
                    {"tool": "code.build_apk", "args": args,
                     "why": "retry the build"},
                ],
            }
        return {"healed": False, "kind": kind,
                "reason": "unknown what file is missing"}

    # ---- bad params: remap and retry ----
    if kind == "bad_params":
        # collect the "got unexpected keyword argument 'X'" info
        wrong = re.search(r"unexpected keyword argument '([^']+)'",
                          error or "")
        wanted = re.search(r"missing \d+ required argument[s]?:?\s*'([^']+)'",
                           error or "")
        new_args = dict(args)
        if wrong and wanted:
            w, n = wrong.group(1), wanted.group(1)
            if w in new_args:
                new_args[n] = new_args.pop(w)
        return {
            "healed": True, "kind": "bad_params",
            "action": "retry_with_renamed_args",
            "retry": True,
            "next_steps": [{"tool": tool_name, "args": new_args,
                            "why": "renamed parameter"}],
        }

    # ---- compile error: use code.fix_flutter ----
    if kind == "compile_error":
        slug = args.get("app_slug") or args.get("project_name") or "app"
        return {
            "healed": True, "kind": "compile_error",
            "action": "fix_and_rebuild",
            "next_steps": [
                {"tool": "code.fix_flutter",
                 "args": {"app_slug": slug, "error_text": error[:2000]},
                 "why": "fix the compile error"},
                {"tool": "code.build_apk",
                 "args": {"app_slug": slug, "spec": (mission_context or {}).get(
                     "command", "")},
                 "why": "rebuild after fix"},
            ],
        }

    # ---- unknown: try writing a new tool ----
    return {
        "healed": False,
        "kind": "unknown",
        "error": error[:300],
        "note": "no known repair strategy",
                  }

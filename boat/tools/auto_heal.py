"""Universal self-healer."""
import json
import re
from . import tool, call_tool


@tool("self.auto_heal", "Universal self-healer for failed steps.",
      {"type": "object", "properties": {
          "failed_step": {"type": "object"},
          "error": {"type": "string"},
          "mission_context": {"type": "object"}},
       "required": ["failed_step", "error"]}, danger="medium")
async def auto_heal(failed_step, error, mission_context=None, **_i):
    e = (error or "").lower()
    tool_name = (failed_step or {}).get("tool", "")
    args = (failed_step or {}).get("args", {})

    if "unknown tool" in e or "keyerror" in e:
        m = re.search(r"unknown tool:\s*([a-z0-9_.]+)", error or "", re.I)
        missing = m.group(1) if m else tool_name
        try:
            await call_tool("self.write_tool", {
                "tool_name": missing,
                "purpose": f"tool {missing} called with {json.dumps(args)}",
                "example_args": args})
            return {"healed": True, "kind": "unknown_tool"}
        except Exception as ex:
            return {"healed": False, "error": str(ex)}

    if "429" in e or "rate" in e or "busy" in e:
        import asyncio
        await asyncio.sleep(15)
        return {"healed": True, "kind": "rate_limit",
                "next_steps": [{"tool": tool_name, "args": args,
                                "why": "retry after wait"}]}

    if "no such file" in e or "not found" in e or "404" in e:
        t = (tool_name or "").lower()
        if "build" in t or "apk" in t:
            slug = args.get("app_slug", "app")
            spec = (mission_context or {}).get("command", "build the app")
            return {"healed": True, "kind": "missing_file",
                    "next_steps": [
                        {"tool": "code.write_flutter_app",
                         "args": {"spec": spec, "app_slug": slug}},
                        {"tool": "code.build_apk",
                         "args": {"app_slug": slug, "spec": spec}}]}

    return {"healed": False, "error": error[:300]}

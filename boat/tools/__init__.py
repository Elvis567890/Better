import inspect

REGISTRY = {}

def tool(name, desc, params=None, danger="low"):
    def deco(fn):
        REGISTRY[name] = {"name": name, "desc": desc, "fn": fn,
                          "params": params or {"type": "object", "properties": {}},
                          "danger": danger}
        return fn
    return deco

def tool_specs():
    return [{"name": v["name"], "description": v["desc"], "parameters": v["params"]}
            for v in REGISTRY.values()]

async def call_tool(name, args):
    if name not in REGISTRY: raise KeyError(f"unknown tool: {name}")
    fn = REGISTRY[name]["fn"]
    if inspect.iscoroutinefunction(fn):
        return await fn(**(args or {}))
    return fn(**(args or {}))

def load_all():
    from . import (shell_tool, browser_tool, phone_tool, gmail_tool,
                   momo_tool, github_tool, social_tool, telegram_tool)

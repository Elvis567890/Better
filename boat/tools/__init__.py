"""Tool registry. Every capability BOAT has is a tool here."""
import inspect

REGISTRY = {}


def tool(name, desc, params=None, danger="low"):
    """Decorator that registers a function as a BOAT tool."""
    def deco(fn):
        REGISTRY[name] = {
            "name": name,
            "desc": desc,
            "fn": fn,
            "params": params or {"type": "object", "properties": {}},
            "danger": danger,
        }
        return fn
    return deco


def tool_specs():
    """Return tool definitions in the shape an LLM expects."""
    return [
        {"name": v["name"], "description": v["desc"], "parameters": v["params"]}
        for v in REGISTRY.values()
    ]


async def call_tool(name, args):
    """Execute a registered tool by name."""
    if name not in REGISTRY:
        raise KeyError(f"unknown tool: {name}")
    fn = REGISTRY[name]["fn"]
    if inspect.iscoroutinefunction(fn):
        return await fn(**(args or {}))
    return fn(**(args or {}))


def load_all():
    """Import every tool module so its decorators register themselves."""
    # Core tools -- always required
    from . import (
        shell_tool,
        browser_tool,
        phone_tool,
        gmail_tool,
        momo_tool,
        github_tool,
        social_tool,
        telegram_tool,
    )

    # Optional tools -- loaded only if the file exists.
    # If any of these raises, the brain still runs with what it has.
    for name in (
        "code_writer",
        "account_creator",
        "ask_tool",
        "phone_agent",
        "payments",
    ):
        try:
            __import__(f"boat.tools.{name}")
        except Exception:
            pass

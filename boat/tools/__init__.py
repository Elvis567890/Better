"""Tool registry. Every capability BOAT has is a tool here.

Each tool module registers itself via the @tool decorator when imported.
load_all() imports every module once so the registry is populated before
the brain runs.
"""
import inspect
import os
import traceback

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
    """Return tool definitions in the shape the LLM expects."""
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
    """Import every tool module so its decorators register themselves.

    Prints real tracebacks when a module fails to load, so the log shows
    exactly which line breaks instead of silently swallowing the error.
    """
    print("[load_all] starting")
    print(f"[load_all] REGISTRY has {len(REGISTRY)} tools before loading")

    # ---- Core tools ----
    core = [
        "shell_tool",
        "browser_tool",
        "phone_tool",
        "gmail_tool",
        "momo_tool",
        "github_tool",
        "social_tool",
        "telegram_tool",
    ]
    for name in core:
        try:
            __import__(f"boat.tools.{name}")
            print(f"[load_all] OK  core/{name}")
        except Exception as e:
            print(f"[load_all] FAIL core/{name}: {e}")
            traceback.print_exc()

    # ---- Bundled tools ----
    bundled = [
        "all_tools",
        "self_builder",
        "accounts_vault",
        "auto_heal",
        "ask_tool",
        "payments",
    ]
    for name in bundled:
        try:
            __import__(f"boat.tools.{name}")
            print(f"[load_all] OK  {name}")
        except Exception as e:
            print(f"[load_all] FAIL {name}: {e}")
            traceback.print_exc()

    # ---- Auto-generated tools ----
    auto_dir = os.path.join(os.path.dirname(__file__), "auto")
    if os.path.isdir(auto_dir):
        for fname in os.listdir(auto_dir):
            if fname.endswith(".py") and not fname.startswith("_"):
                mod = fname[:-3]
                try:
                    __import__(f"boat.tools.auto.{mod}")
                    print(f"[load_all] OK  auto/{mod}")
                except Exception as e:
                    print(f"[load_all] FAIL auto/{mod}: {e}")
                    traceback.print_exc()

    print(f"[load_all] done, REGISTRY has {len(REGISTRY)} tools")
    if REGISTRY:
        print(f"[load_all] tools: {sorted(REGISTRY.keys())}")

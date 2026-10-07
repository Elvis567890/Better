"""Tool registry."""
import inspect
import os
import traceback

REGISTRY = {}


def tool(name, desc, params=None, danger="low"):
    def deco(fn):
        REGISTRY[name] = {
            "name": name, "desc": desc, "fn": fn,
            "params": params or {"type": "object", "properties": {}},
            "danger": danger,
        }
        return fn
    return deco


def tool_specs():
    return [{"name": v["name"], "description": v["desc"],
             "parameters": v["params"]} for v in REGISTRY.values()]


async def call_tool(name, args):
    if name not in REGISTRY:
        raise KeyError(f"unknown tool: {name}")
    fn = REGISTRY[name]["fn"]
    if inspect.iscoroutinefunction(fn):
        return await fn(**(args or {}))
    return fn(**(args or {}))


def load_all():
    print("[load_all] starting")
    for name in ("shell_tool", "browser_tool", "phone_tool",
                 "gmail_tool", "momo_tool", "github_tool",
                 "social_tool", "telegram_tool"):
        try:
            __import__(f"boat.tools.{name}")
        except Exception as e:
            print(f"[load_all] FAIL core/{name}: {e}")
            traceback.print_exc()
    for name in ("all_tools", "self_builder", "accounts_vault",
                 "auto_heal", "ask_tool", "payments", "big_project"):
        try:
            __import__(f"boat.tools.{name}")
            print(f"[load_all] OK  {name}")
        except Exception as e:
            print(f"[load_all] FAIL {name}: {e}")
            traceback.print_exc()
    auto_dir = os.path.join(os.path.dirname(__file__), "auto")
    if os.path.isdir(auto_dir):
        for fname in os.listdir(auto_dir):
            if fname.endswith(".py") and not fname.startswith("_"):
                try:
                    __import__(f"boat.tools.auto.{fname[:-3]}")
                except Exception as e:
                    print(f"[load_all] FAIL auto/{fname}: {e}")
    print(f"[load_all] done. REGISTRY has {len(REGISTRY)} tools")

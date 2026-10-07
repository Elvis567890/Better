"""Big project tracker."""
import json
import os
import re
import time
import uuid
import httpx
from . import tool


async def _llm(prompt, max_tokens=4000):
    base = os.environ.get("BOAT_LLM_BASE", "https://api.groq.com/openai/v1")
    key = os.environ["BOAT_LLM_KEY"]
    model = os.environ.get("BOAT_LLM_MODEL", "llama-3.3-70b-versatile")
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model,
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.2, "max_tokens": max_tokens})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def _json(s):
    if not s: return {}
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    try: return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, re.S)
        if not m: return {}
        try: return json.loads(m.group(0))
        except Exception: return {}


def _db():
    from ..memory import Memory
    m = Memory()
    m.db.executescript("""CREATE TABLE IF NOT EXISTS big_projects(
        id TEXT PRIMARY KEY, title TEXT, goal TEXT, platform TEXT,
        total_sprints INTEGER, done_sprints INTEGER,
        current_sprint INTEGER, sprint_list TEXT, status TEXT,
        slug TEXT, created REAL, updated REAL);""")
    m.db.commit()
    return m


def _slugify(s):
    s = (s or "bigproj").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")[:40] or "bigproj"


@tool("big.start", "Start a BIG project split into sprints.",
      {"type": "object", "properties": {
          "title": {"type": "string"}, "goal": {"type": "string"},
          "platform": {"type": "string"},
          "max_sprints": {"type": "integer", "default": 20}},
       "required": ["title", "goal"]}, danger="high")
async def start(title, goal, platform="android", max_sprints=20, **_i):
    slug = _slugify(title)
    raw = await _llm(
        f"Break this into {max_sprints} sprints.\n"
        f"Project: {title}\nGoal: {goal}\nPlatform: {platform}\n"
        f'Return ONLY JSON: {{"sprints":[{{"n":1,"title":"..","deliverable":".."}}]}}')
    data = _json(raw)
    sprints = data.get("sprints") or []
    if not sprints:
        return {"ok": False, "error": "no sprints"}
    m = _db()
    pid = uuid.uuid4().hex[:8]
    now = time.time()
    m.db.execute(
        "INSERT INTO big_projects(id,title,goal,platform,total_sprints,"
        "done_sprints,current_sprint,sprint_list,status,slug,created,updated) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (pid, title, goal, platform, len(sprints), 0, 1,
         json.dumps(sprints), "active", slug, now, now))
    m.db.commit()
    return {"ok": True, "project_id": pid, "sprint_count": len(sprints),
            "first_sprint": sprints[0]}


@tool("big.next", "Run the next sprint of a big project.",
      {"type": "object", "properties": {"project_id": {"type": "string"}}},
      danger="high")
async def next_sprint(project_id=None, **_i):
    m = _db()
    if project_id:
        row = m.db.execute(
            "SELECT id,title,goal,platform,total_sprints,done_sprints,"
            "current_sprint,sprint_list,slug FROM big_projects WHERE id=?",
            (project_id,)).fetchone()
    else:
        row = m.db.execute(
            "SELECT id,title,goal,platform,total_sprints,done_sprints,"
            "current_sprint,sprint_list,slug FROM big_projects "
            "WHERE status='active' ORDER BY updated DESC LIMIT 1").fetchone()
    if not row:
        return {"ok": False, "reason": "no active project"}
    (pid, title, goal, platform, total, done_count, cur, sprint_list, slug) = row
    sprints = json.loads(sprint_list or "[]")
    if cur > total:
        m.db.execute("UPDATE big_projects SET status='done',updated=? WHERE id=?",
                     (time.time(), pid))
        m.db.commit()
        return {"ok": True, "status": "done"}
    this_sprint = sprints[cur - 1] if cur <= len(sprints) else None
    if not this_sprint:
        return {"ok": False, "reason": "no more sprints"}
    from . import call_tool
    spec = (f"Sprint {cur} of {total} for '{title}'.\n"
            f"Goal: {goal}\nSprint: {this_sprint.get('title')}\n"
            f"Deliverable: {this_sprint.get('deliverable')}\n\n"
            f"Write FULL main.dart including sprints 1 through {cur}.")
    try:
        wr = await call_tool("code.write_flutter_app",
                             {"spec": spec, "app_slug": slug})
    except Exception as e:
        return {"ok": False, "error": str(e)}
    m.db.execute("UPDATE big_projects SET done_sprints=?,"
                 "current_sprint=?,updated=? WHERE id=?",
                 (done_count + 1, cur + 1, time.time(), pid))
    m.db.commit()
    return {"ok": True, "sprint_completed": cur,
            "sprint_title": this_sprint.get("title"),
            "next_sprint": cur + 1}

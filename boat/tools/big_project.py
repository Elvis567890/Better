"""Big project builder. Break a large goal into sprints, build one per run.

Example:
  Boat, start big project: build a simple 2D football game for Android.
  → BOAT creates a project, splits it into 20 sprints
  → Each run completes one sprint
  → After 20 runs (a few days), the app is done and APK is delivered
"""
import json
import os
import time
import uuid

import httpx

from . import tool


async def _llm(prompt, max_tokens=6000):
    base = os.environ.get("BOAT_LLM_BASE", "https://api.groq.com/openai/v1")
    key = os.environ["BOAT_LLM_KEY"]
    model = os.environ.get("BOAT_LLM_MODEL", "llama-3.3-70b-versatile")
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": max_tokens,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def _json(s):
    import re
    if not s:
        return {}
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, re.S)
        if not m:
            return {}
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}


def _db():
    from .memory import Memory
    m = Memory()
    m.db.executescript("""
    CREATE TABLE IF NOT EXISTS big_projects(
      id TEXT PRIMARY KEY,
      title TEXT,
      goal TEXT,
      platform TEXT,
      total_sprints INTEGER,
      done_sprints INTEGER,
      current_sprint INTEGER,
      sprint_list TEXT,
      status TEXT,
      slug TEXT,
      created REAL,
      updated REAL
    );
    """)
    m.db.commit()
    return m


def _slugify(s):
    import re
    s = (s or "bigproj").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")[:40] or "bigproj"


@tool(
    "big.start",
    "Start a BIG project. BOAT splits it into sprints automatically, then "
    "completes one sprint per run. Use for games, real apps, platforms.",
    {"type": "object", "properties": {
        "title": {"type": "string",
                  "description": "e.g. '2D football game' or 'Uber-clone for Kampala'"},
        "goal": {"type": "string",
                 "description": "what done looks like"},
        "platform": {"type": "string",
                     "description": "android | web | python | other"},
        "max_sprints": {"type": "integer", "default": 20},
    }, "required": ["title", "goal"]},
    danger="high",
)
async def start(title, goal, platform="android", max_sprints=20, **_i):
    slug = _slugify(title)

    prompt = f"""You are a senior software architect.

Big project: {title}
Goal: {goal}
Platform: {platform}

Break this into {max_sprints} SMALL sprints. Each sprint must:
- Be doable in one focused work session
- Produce a runnable increment
- Build on the previous sprint
- Not require >3 files of new code

Return ONLY JSON:
{{
  "sprints": [
    {{"n": 1, "title": "short title", "deliverable": "what works at the end"}},
    {{"n": 2, "title": "...", "deliverable": "..."}}
  ]
}}
"""
    try:
        raw = await _llm(prompt, max_tokens=4000)
    except Exception as e:
        return {"ok": False, "error": f"llm failed: {e}"}

    data = _json(raw)
    sprints = data.get("sprints") or []
    if not sprints:
        return {"ok": False, "error": "no sprints generated",
                "head": (raw or "")[:400]}

    m = _db()
    pid = uuid.uuid4().hex[:8]
    now = time.time()
    m.db.execute(
        "INSERT INTO big_projects(id,title,goal,platform,total_sprints,"
        "done_sprints,current_sprint,sprint_list,status,slug,created,updated)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (pid, title, goal, platform, len(sprints), 0, 1,
         json.dumps(sprints), "active", slug, now, now))
    m.db.commit()

    return {
        "ok": True,
        "project_id": pid,
        "title": title,
        "sprint_count": len(sprints),
        "first_sprint": sprints[0] if sprints else None,
        "note": "each run will complete one sprint",
    }


@tool(
    "big.next",
    "Run the next sprint of a big project. Call this every cycle to advance "
    "the project by one sprint.",
    {"type": "object", "properties": {
        "project_id": {"type": "string"},
    }, "required": []},
    danger="high",
)
async def next_sprint(project_id=None, **_i):
    m = _db()
    if project_id:
        row = m.db.execute(
            "SELECT id,title,goal,platform,total_sprints,done_sprints,"
            "current_sprint,sprint_list,slug FROM big_projects "
            "WHERE id=?", (project_id,)).fetchone()
    else:
        row = m.db.execute(
            "SELECT id,title,goal,platform,total_sprints,done_sprints,"
            "current_sprint,sprint_list,slug FROM big_projects "
            "WHERE status='active' ORDER BY updated DESC LIMIT 1").fetchone()

    if not row:
        return {"ok": False, "reason": "no active big project"}

    (pid, title, goal, platform, total, done_count, cur, sprint_list,
     slug) = row
    sprints = json.loads(sprint_list or "[]")

    if cur > total:
        m.db.execute("UPDATE big_projects SET status='done',updated=? "
                     "WHERE id=?", (time.time(), pid))
        m.db.commit()
        return {"ok": True, "status": "done",
                "title": title, "total_sprints": total}

    this_sprint = sprints[cur - 1] if cur <= len(sprints) else None
    if not this_sprint:
        return {"ok": False, "reason": "sprint list exhausted"}

    # execute the sprint: for android, write the next version of the app
    from . import call_tool

    if platform == "android":
        # each sprint rewrites main.dart to add the next feature
        spec = (
            f"This is sprint {cur} of {total} for '{title}'.\n"
            f"Overall goal: {goal}\n"
            f"Sprint {cur}: {this_sprint.get('title')}\n"
            f"Deliverable: {this_sprint.get('deliverable')}\n\n"
            "Write the FULL current main.dart that includes this sprint's "
            "feature PLUS all previous features (sprints 1 through "
            f"{cur}). Keep it a working Flutter app."
        )
        try:
            wr = await call_tool("code.write_flutter_app", {
                "spec": spec,
                "app_slug": slug,
                "app_name": title[:30],
            })
        except Exception as e:
            return {"ok": False, "error": str(e), "sprint": cur}

        # once every 5 sprints, also ship a test APK
        if cur % 5 == 0 or cur == total:
            try:
                await call_tool("code.build_apk", {
                    "app_slug": slug, "spec": spec,
                })
            except Exception:
                pass

        m.db.execute(
            "UPDATE big_projects SET done_sprints=?,current_sprint=?,"
            "updated=? WHERE id=?",
            (done_count + 1, cur + 1, time.time(), pid))
        m.db.commit()

        return {
            "ok": True,
            "project_id": pid,
            "sprint_completed": cur,
            "sprint_title": this_sprint.get("title"),
            "next_sprint": cur + 1 if cur < total else None,
            "progress": f"{cur}/{total}",
            "write_result": wr,
        }

    # other platforms: not yet implemented
    return {"ok": False, "reason": f"platform {platform} not supported yet"}


@tool(
    "big.status",
    "Show the status of all big projects.",
    {"type": "object", "properties": {}},
    danger="low",
)
async def status(**_i):
    m = _db()
    rows = m.db.execute(
        "SELECT id,title,status,current_sprint,total_sprints "
        "FROM big_projects ORDER BY updated DESC").fetchall()
    return {
        "ok": True,
        "projects": [
            {"id": r[0], "title": r[1], "status": r[2],
             "progress": f"{r[3]-1}/{r[4]}" if r[2] == "active"
                         else f"{r[4]}/{r[4]}"}
            for r in rows
        ],
}

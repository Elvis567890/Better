import json, os, sqlite3, time

SCHEMA = """
CREATE TABLE IF NOT EXISTS missions(
  id TEXT PRIMARY KEY, command TEXT, source TEXT, status TEXT,
  money_today REAL DEFAULT 0, pivots INTEGER DEFAULT 0,
  created REAL, updated REAL, meta TEXT);
CREATE TABLE IF NOT EXISTS payments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mission_id TEXT, source TEXT, amount REAL, currency TEXT,
  ref TEXT, verified INTEGER DEFAULT 0, ts REAL);
CREATE TABLE IF NOT EXISTS opportunities(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT, url TEXT, pays_today INTEGER, cost REAL,
  eta_hours REAL, notes TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS lessons(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mission_id TEXT, kind TEXT, text TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
"""

class Memory:
    def __init__(self, path=None):
        self.path = path or os.environ.get("BOAT_DB", "boat.db")
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.executescript(SCHEMA); self.db.commit()

    def create_mission(self, mid, command, source):
        now = time.time()
        self.db.execute("INSERT INTO missions(id,command,source,status,created,updated) VALUES(?,?,?,?,?,?)",
                        (mid, command, source, "thinking", now, now))
        self.db.commit()

    def update_mission(self, mid, **kw):
        if not kw: return
        cols = ", ".join(f"{k}=?" for k in kw)
        self.db.execute(f"UPDATE missions SET {cols}, updated=? WHERE id=?",
                        (*kw.values(), time.time(), mid))
        self.db.commit()

    def record_payment(self, mid, source, amount, currency="USD", ref="", verified=0):
        self.db.execute("INSERT INTO payments(mission_id,source,amount,currency,ref,verified,ts) VALUES(?,?,?,?,?,?,?)",
                        (mid, source, amount, currency, ref, verified, time.time()))
        self.db.commit()

    def money_today(self):
        start = time.time() - 86400
        cur = self.db.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE verified=1 AND ts>=?", (start,))
        return float(cur.fetchone()[0] or 0)

    def add_lesson(self, mid, kind, text):
        self.db.execute("INSERT INTO lessons(mission_id,kind,text,ts) VALUES(?,?,?,?)",
                        (mid, kind, text, time.time())); self.db.commit()

    def add_opportunity(self, title, url, pays_today, cost, eta_hours, notes=""):
        self.db.execute("INSERT INTO opportunities(title,url,pays_today,cost,eta_hours,notes,ts) VALUES(?,?,?,?,?,?,?)",
                        (title, url, int(pays_today), cost, eta_hours, notes, time.time()))
        self.db.commit()

    def recent_context(self, n=5):
        missions = self.db.execute("SELECT id, command, status, money_today FROM missions ORDER BY created DESC LIMIT ?", (n,)).fetchall()
        lessons = self.db.execute("SELECT kind, text FROM lessons ORDER BY ts DESC LIMIT 10").fetchall()
        return {
            "recent_missions": [{"id": m[0], "command": m[1], "status": m[2], "money_today": m[3]} for m in missions],
            "lessons": [{"kind": l[0], "text": l[1]} for l in lessons],
            "money_today_total": self.money_today(),
        }

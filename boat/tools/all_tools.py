"""BOAT - every tool in one file.

Includes full Android scaffolding so Flutter apps actually compile into APKs.
Uses dynamic model discovery so it never 404s on a retired model name.
"""
import asyncio
import base64
import json
import os
import re
import time
import uuid

import httpx

from . import tool


GH = "https://api.github.com"


# ==================================================================
# GitHub helpers
# ==================================================================
def _gh_headers():
    return {
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN', '')}",
        "Accept": "application/vnd.github+json",
    }


async def _gh_get(repo, path):
    try:
        async with httpx.AsyncClient(timeout=30, headers=_gh_headers()) as c:
            r = await c.get(f"{GH}/repos/{repo}/contents/{path}")
            if r.status_code != 200:
                return None
            return r.json()
    except Exception:
        return None


async def _gh_put(repo, path, content, message):
    try:
        async with httpx.AsyncClient(timeout=30, headers=_gh_headers()) as c:
            sha = None
            r = await c.get(f"{GH}/repos/{repo}/contents/{path}")
            if r.status_code == 200:
                sha = r.json().get("sha")
            body = {
                "message": message,
                "content": base64.b64encode(content.encode()).decode(),
            }
            if sha:
                body["sha"] = sha
            r = await c.put(f"{GH}/repos/{repo}/contents/{path}", json=body)
            return r.status_code in (200, 201)
    except Exception as e:
        print(f"[all_tools] push failed: {e}")
        return False


async def _gh_exists(repo, path):
    return (await _gh_get(repo, path)) is not None


# ==================================================================
# LLM with model discovery
# ==================================================================
_MODEL_CACHE = {"list": None, "picked": None}


async def _discover_models():
    if _MODEL_CACHE["picked"]:
        return _MODEL_CACHE["picked"]

    base = os.environ.get("BOAT_LLM_BASE", "https://api.groq.com/openai/v1")
    key = os.environ["BOAT_LLM_KEY"]

    preferred = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "meta-llama/llama-4-scout-17b-16e-instruct",
    ]

    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{base}/models",
                            headers={"Authorization": f"Bearer {key}"})
            r.raise_for_status()
            data = r.json()
            ids = [m.get("id") or m.get("name") or ""
                   for m in (data.get("data") or data.get("models") or [])]
            ids = [i for i in ids if i]
            for want in preferred:
                if want in ids:
                    _MODEL_CACHE["picked"] = want
                    print(f"[all_tools] model picked: {want}")
                    return want
            if ids:
                _MODEL_CACHE["picked"] = ids[0]
                print(f"[all_tools] model picked (fallback): {ids[0]}")
                return ids[0]
    except Exception as e:
        print(f"[all_tools] discovery failed: {e}")

    fallback = os.environ.get("BOAT_LLM_MODEL",
                              "llama-3.3-70b-versatile")
    _MODEL_CACHE["picked"] = fallback
    print(f"[all_tools] model picked (env fallback): {fallback}")
    return fallback


async def _llm(prompt, max_tokens=12000, temp=0.2):
    base = os.environ.get("BOAT_LLM_BASE", "https://api.groq.com/openai/v1")
    key = os.environ["BOAT_LLM_KEY"]

    candidates = []
    top = await _discover_models()
    if top:
        candidates.append(top)
    env_model = os.environ.get("BOAT_LLM_MODEL")
    if env_model and env_model not in candidates:
        candidates.append(env_model)
    for m in ("llama-3.3-70b-versatile", "llama-3.1-8b-instant"):
        if m not in candidates:
            candidates.append(m)

    last_error = None
    for model in candidates:
        try:
            async with httpx.AsyncClient(timeout=180) as c:
                r = await c.post(
                    f"{base}/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temp,
                        "max_tokens": max_tokens,
                    },
                )
                if r.status_code == 404:
                    print(f"[all_tools] {model} 404, next")
                    last_error = f"404 {model}"
                    continue
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            last_error = str(e)[:200]
            print(f"[all_tools] {model} failed: {last_error}")
            continue

    raise RuntimeError(f"all models failed. last: {last_error}")


def _slugify(s):
    s = (s or "item").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "item"


def _pick(*vals, default=None):
    for v in vals:
        if v:
            return v
    return default


def _parse_files(raw):
    raw = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(),
                 flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None


def _db():
    from .memory import Memory
    m = Memory()
    m.db.executescript("""
    CREATE TABLE IF NOT EXISTS projects(
      id TEXT PRIMARY KEY, title TEXT, goal TEXT, status TEXT,
      stage TEXT, plan TEXT, done TEXT, blocked TEXT, notes TEXT,
      created REAL, updated REAL);
    CREATE TABLE IF NOT EXISTS leads(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT, contact TEXT, channel TEXT, region TEXT, pitch TEXT,
      status TEXT, created REAL, updated REAL);
    """)
    m.db.commit()
    return m


# ==================================================================
# Flutter app - write (WITH FULL ANDROID SCAFFOLDING)
# ==================================================================
@tool("code.write_flutter_app",
      "Write a complete Flutter app - including Android scaffolding - "
      "and push it to apps/<slug>/. Required for the APK to compile.",
      {"type": "object", "properties": {
          "spec": {"type": "string"},
          "app_slug": {"type": "string"},
          "project_name": {"type": "string"},
          "app_name": {"type": "string"},
          "package_name": {"type": "string"},
      }, "required": ["spec"]},
      danger="high")
async def write_flutter_app(spec, app_slug=None, project_name=None,
                            app_name=None, package_name=None, **_i):
    slug = _slugify(_pick(app_slug, project_name, app_name, "app"))
    app_name = _pick(app_name, project_name,
                     slug.replace("_", " ").title().replace(" ", ""))
    package_name = _pick(package_name, f"com.boat.{slug}")

    prompt = f"""You are a senior Flutter engineer.
Write a COMPLETE, COMPILABLE Flutter app that can build an APK.

--- SPEC ---
{spec}
--- END SPEC ---

App name: {app_name}
Package name: {package_name}

Return ONLY a JSON object with EXACTLY these files:

{{
  "files": {{
    "pubspec.yaml": "<full pubspec.yaml>",
    "lib/main.dart": "<full Dart code>",
    "analysis_options.yaml": "<basic analysis options>",
    "android/app/build.gradle": "<full gradle file>",
    "android/build.gradle": "<full gradle file>",
    "android/settings.gradle": "<full gradle file>",
    "android/gradle.properties": "<full gradle properties>",
    "android/app/src/main/AndroidManifest.xml": "<full manifest>",
    "android/app/src/main/kotlin/MainActivity.kt": "<Kotlin MainActivity>"
  }}
}}

CRITICAL RULES - the APK build will fail if you miss any:
1. Every file MUST be complete and valid.
2. Flutter 3.22+, Dart 3.4+, minSdk 21, targetSdk 34.
3. Package/applicationId: {package_name}
4. pubspec.yaml must have exactly this structure:
     name: {slug}
     description: A simple Flutter app
     publish_to: 'none'
     version: 1.0.0+1
     environment:
       sdk: '>=3.4.0 <4.0.0'
     dependencies:
       flutter:
         sdk: flutter
       cupertino_icons: ^1.0.6
     dev_dependencies:
       flutter_test:
         sdk: flutter
       flutter_lints: ^4.0.0
     flutter:
       uses-material-design: true
5. main.dart must compile with Flutter 3.22+. Use Material 3.
6. android/settings.gradle must use the modern Flutter plugin format:
     pluginManagement {{
         def flutterSdkPath = {{
             def properties = new Properties()
             file("local.properties").withInputStream {{ properties.load(it) }}
             def flutterSdkPath = properties.getProperty("flutter.sdk")
             assert flutterSdkPath != null, "flutter.sdk not set in local.properties"
             return flutterSdkPath
         }}()
         includeBuild("$flutterSdkPath/packages/flutter_tools/gradle")
         repositories {{ google(); mavenCentral(); gradlePluginPortal() }}
     }}
     plugins {{
         id "dev.flutter.flutter-plugin-loader" version "1.0.0"
         id "com.android.application" version "8.1.0" apply false
         id "org.jetbrains.kotlin.android" version "1.9.22" apply false
     }}
     include ":app"
7. android/build.gradle must be minimal:
     allprojects {{
         repositories {{ google(); mavenCentral() }}
     }}
     rootProject.buildDir = "../build"
     subprojects {{ project.buildDir = "${{rootProject.buildDir}}/${{project.name}}" }}
     subprojects {{ project.evaluationDependsOn(":app") }}
     tasks.register("clean", Delete) {{ delete rootProject.buildDir }}
8. android/app/build.gradle must use the modern plugin loader:
     plugins {{
         id "com.android.application"
         id "kotlin-android"
         id "dev.flutter.flutter-gradle-plugin"
     }}
     android {{
         namespace = "{package_name}"
         compileSdk = 34
         ndkVersion = flutter.ndkVersion
         compileOptions {{ sourceCompatibility = JavaVersion.VERSION_17
                          targetCompatibility = JavaVersion.VERSION_17 }}
         kotlinOptions {{ jvmTarget = "17" }}
         defaultConfig {{
             applicationId = "{package_name}"
             minSdk = 21
             targetSdk = 34
             versionCode = flutter.versionCode
             versionName = flutter.versionName
         }}
         buildTypes {{
             release {{
                 signingConfig = signingConfigs.debug
             }}
         }}
     }}
     flutter {{ source = "../.." }}
9. android/gradle.properties:
     org.gradle.jvmargs=-Xmx4G -XX:MaxMetaspaceSize=2G
     android.useAndroidX=true
     android.enableJetifier=true
10. AndroidManifest.xml at android/app/src/main/:
     <manifest xmlns:android="http://schemas.android.com/apk/res/android">
       <application android:label="{app_name}" android:name="${{applicationName}}"
                    android:icon="@mipmap/ic_launcher">
         <activity android:name=".MainActivity"
                   android:exported="true"
                   android:launchMode="singleTop"
                   android:theme="@style/LaunchTheme"
                   android:configChanges="orientation|keyboardHidden|keyboard|screenSize|smallestScreenSize|locale|layoutDirection|fontScale|screenLayout|density|uiMode"
                   android:hardwareAccelerated="true"
                   android:windowSoftInputMode="adjustResize">
           <meta-data android:name="io.flutter.embedding.android.NormalTheme"
                      android:resource="@style/NormalTheme" />
           <intent-filter>
             <action android:name="android.intent.action.MAIN"/>
             <category android:name="android.intent.category.LAUNCHER"/>
           </intent-filter>
         </activity>
         <meta-data android:name="flutterEmbedding"
                    android:value="2" />
       </application>
       <queries>
         <intent>
           <action android:name="android.intent.action.PROCESS_TEXT"/>
           <data android:mimeType="text/plain"/>
         </intent>
       </queries>
     </manifest>
11. MainActivity.kt at android/app/src/main/kotlin/:
     package {package_name}
     import io.flutter.embedding.android.FlutterActivity
     class MainActivity: FlutterActivity()
12. analysis_options.yaml: include: package:flutter_lints/flutter.yaml
13. No TODOs. No placeholders. No truncation.

Return ONLY the JSON. No prose. No code fences.
"""
    try:
        raw = await _llm(prompt, max_tokens=12000)
    except Exception as e:
        return {"ok": False, "error": f"llm failed: {e}"}
    data = _parse_files(raw)
    if not data or not isinstance(data.get("files"), dict):
        return {"ok": False, "error": "no files",
                "head": (raw or "")[:400]}

    repo = os.environ["GITHUB_REPOSITORY"]
    pushed = []
    for rel, content in data["files"].items():
        ok = await _gh_put(repo, f"apps/{slug}/{rel}", content,
                           f"boat: write {slug}/{rel}")
        pushed.append({"path": rel, "ok": ok})

    # verify the essential files exist
    need = [
        "pubspec.yaml",
        "lib/main.dart",
        "android/app/build.gradle",
        "android/build.gradle",
        "android/settings.gradle",
        "android/app/src/main/AndroidManifest.xml",
    ]
    missing = []
    for rel in need:
        if not await _gh_exists(repo, f"apps/{slug}/{rel}"):
            missing.append(rel)

    if missing:
        return {"ok": False, "error": "essential files missing",
                "missing": missing, "pushed": pushed}

    return {"ok": True, "app_slug": slug, "app_name": app_name,
            "package_name": package_name,
            "files_written": len(pushed),
            "files": [p["path"] for p in pushed]}


# ==================================================================
# Flutter app - build
# ==================================================================
@tool("code.build_apk",
      "Compile an app already in the repo to APK. Self-heals if the app "
      "folder is missing and a spec is provided.",
      {"type": "object", "properties": {
          "app_slug": {"type": "string"},
          "project_name": {"type": "string"},
          "app_name": {"type": "string"},
          "package_name": {"type": "string"},
          "chat_id": {"type": "string"},
          "spec": {"type": "string"},
      }, "required": []},
      danger="high")
async def build_apk(app_slug=None, project_name=None, app_name=None,
                    package_name=None, chat_id=None, spec=None, **_i):
    slug = _slugify(_pick(app_slug, project_name, app_name, "app"))
    app_name = _pick(app_name, project_name,
                     slug.replace("_", " ").title().replace(" ", ""))
    package_name = _pick(package_name, f"com.boat.{slug}")
    chat_id = _pick(chat_id, os.environ.get("TELEGRAM_ALLOWED", ""))
    repo = os.environ["GITHUB_REPOSITORY"]

    if not await _gh_exists(repo, f"apps/{slug}/pubspec.yaml"):
        if not spec:
            return {"ok": False,
                    "error": f"apps/{slug} missing and no spec",
                    "next_action": "call code.write_flutter_app first"}
        wr = await write_flutter_app(spec=spec, app_slug=slug,
                                     app_name=app_name,
                                     package_name=package_name)
        if not wr.get("ok"):
            return {"ok": False, "error": "self-heal write failed",
                    "detail": wr}

    try:
        async with httpx.AsyncClient(timeout=30,
                                     headers=_gh_headers()) as c:
            r = await c.post(
                f"{GH}/repos/{repo}/actions/workflows/"
                f"boat-build-apk.yml/dispatches",
                json={"ref": "main", "inputs": {
                    "app_dir": f"apps/{slug}", "app_name": app_name,
                    "package_name": package_name,
                    "chat_id": str(chat_id)}},
            )
            return {"ok": r.status_code == 204, "app_slug": slug,
                    "status": r.status_code,
                    "note": "APK build started"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ==================================================================
# Fix a Flutter build failure
# ==================================================================
@tool("code.fix_flutter",
      "Given a Flutter compile error, rewrite the offending files.",
      {"type": "object", "properties": {
          "app_slug": {"type": "string"},
          "error_text": {"type": "string"},
      }, "required": ["app_slug", "error_text"]}, danger="high")
async def fix_flutter(app_slug, error_text, **_i):
    slug = _slugify(app_slug)
    repo = os.environ["GITHUB_REPOSITORY"]

    main = await _gh_get(repo, f"apps/{slug}/lib/main.dart")
    pubspec = await _gh_get(repo, f"apps/{slug}/pubspec.yaml")
    if not main:
        return {"ok": False, "error": "main.dart missing"}

    main_text = base64.b64decode(main["content"]).decode(errors="ignore")
    pubspec_text = (base64.b64decode(pubspec["content"]).decode(
        errors="ignore") if pubspec else "")

    prompt = f"""Fix this Flutter project so it compiles.

ERROR:
{error_text[:2000]}

CURRENT pubspec.yaml:
{pubspec_text[:1500]}

CURRENT lib/main.dart:
{main_text[:5000]}

If the error mentions a MISSING file (like android/app/build.gradle),
return ALL the android files needed:
  android/app/build.gradle
  android/build.gradle
  android/settings.gradle
  android/gradle.properties
  android/app/src/main/AndroidManifest.xml

Otherwise only return the files you changed.

Return ONLY JSON:
{{"files": {{"<path>": "<content>"}}}}
"""
    try:
        raw = await _llm(prompt, max_tokens=12000)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    data = _parse_files(raw)
    if not data or not isinstance(data.get("files"), dict):
        return {"ok": False, "error": "could not produce fix"}
    for rel, content in data["files"].items():
        await _gh_put(repo, f"apps/{slug}/{rel}", content,
                      f"boat: fix {slug}/{rel}")
    return {"ok": True, "fixed_files": list(data["files"].keys())}


# ==================================================================
# Self check
# ==================================================================
@tool("self.verify",
      "Verify that a task's artifact exists.",
      {"type": "object", "properties": {
          "artifact_kind": {"type": "string"},
          "identifier": {"type": "string"},
          "path": {"type": "string"},
      }, "required": ["artifact_kind", "identifier"]},
      danger="low")
async def verify(artifact_kind, identifier, path=None, **_i):
    repo = os.environ["GITHUB_REPOSITORY"]
    slug = _slugify(identifier)
    if artifact_kind == "app":
        ok = (await _gh_exists(repo, f"apps/{slug}/pubspec.yaml")
              and await _gh_exists(repo, f"apps/{slug}/lib/main.dart"))
        return {"ok": ok, "kind": "app", "slug": slug}
    if artifact_kind == "website":
        return {"ok": await _gh_exists(repo, f"sites/{slug}/index.html")}
    if artifact_kind == "document":
        return {"ok": await _gh_exists(repo, f"docs/{slug}.md")}
    if artifact_kind == "script":
        for ext in ("py", "js", "sh"):
            if await _gh_exists(repo, f"scripts/{slug}/main.{ext}"):
                return {"ok": True, "kind": "script", "slug": slug}
        return {"ok": False, "kind": "script", "slug": slug}
    if artifact_kind == "file" and path:
        return {"ok": await _gh_exists(repo, path)}
    return {"ok": False, "reason": "unknown kind"}


# ==================================================================
# Websites, docs, scripts
# ==================================================================
@tool("make.website",
      "Build a complete HTML/CSS/JS website from a spec.",
      {"type": "object", "properties": {
          "spec": {"type": "string"}, "slug": {"type": "string"},
          "project_name": {"type": "string"},
      }, "required": ["spec"]}, danger="high")
async def make_website(spec, slug=None, project_name=None, **_i):
    slug = _slugify(_pick(slug, project_name, "site"))
    prompt = f"""Build a COMPLETE, working website.

SPEC:
{spec}

Return ONLY JSON:
{{"files": {{"index.html": "...", "style.css": "...", "script.js": "..."}}}}

Plain HTML/CSS/JS only. Mobile-responsive. Self-contained.
"""
    raw = await _llm(prompt, max_tokens=8000)
    data = _parse_files(raw)
    if not data or not isinstance(data.get("files"), dict):
        return {"ok": False, "error": "no files"}
    repo = os.environ["GITHUB_REPOSITORY"]
    for rel, content in data["files"].items():
        await _gh_put(repo, f"sites/{slug}/{rel}", content,
                      f"boat: write {slug}/{rel}")
    owner, reponame = repo.split("/", 1)
    return {"ok": True, "slug": slug,
            "files": list(data["files"].keys()),
            "url": f"https://{owner.lower()}.github.io/{reponame}/{slug}/"}


@tool("make.document",
      "Write a document (pitch, article, proposal, README).",
      {"type": "object", "properties": {
          "spec": {"type": "string"}, "slug": {"type": "string"},
          "title": {"type": "string"},
      }, "required": ["spec"]}, danger="medium")
async def make_document(spec, slug=None, title=None, **_i):
    slug = _slugify(_pick(slug, "doc"))
    title = title or slug.replace("_", " ").title()
    body = await _llm(
        f"Write a complete document.\nTitle: {title}\nSpec: {spec}\n\n"
        f"Return ONLY Markdown, starting with # {title}",
        max_tokens=6000)
    repo = os.environ["GITHUB_REPOSITORY"]
    await _gh_put(repo, f"docs/{slug}.md", body, f"boat: write {slug}")
    return {"ok": True, "path": f"docs/{slug}.md", "chars": len(body)}


@tool("make.script",
      "Write a script (python/javascript/bash).",
      {"type": "object", "properties": {
          "spec": {"type": "string"}, "language": {"type": "string"},
          "slug": {"type": "string"},
      }, "required": ["spec", "language"]}, danger="high")
async def make_script(spec, language, slug=None, **_i):
    slug = _slugify(_pick(slug, "script"))
    ext = {"python": "py", "py": "py", "javascript": "js",
           "js": "js", "bash": "sh", "sh": "sh"}.get(language.lower(), "txt")
    code = await _llm(
        f"Write a COMPLETE, WORKING {language} script.\nSpec: {spec}\n\n"
        f"Return ONLY the raw code.",
        max_tokens=6000)
    code = re.sub(r"^```[a-z]*\n?", "", code)
    code = re.sub(r"\n?```$", "", code)
    repo = os.environ["GITHUB_REPOSITORY"]
    path = f"scripts/{slug}/main.{ext}"
    await _gh_put(repo, path, code, f"boat: write {path}")
    return {"ok": True, "path": path, "language": language}


@tool("make.any",
      "Escape hatch: LLM writes any files to any repo folder.",
      {"type": "object", "properties": {
          "spec": {"type": "string"}, "target_dir": {"type": "string"},
      }, "required": ["spec", "target_dir"]}, danger="high")
async def make_any(spec, target_dir, **_i):
    target_dir = target_dir.strip("/").replace(" ", "_")
    raw = await _llm(
        f"Produce the files for this task.\nSpec: {spec}\n\n"
        f'Return ONLY JSON: {{"files": {{"<path>": "<content>"}}}}',
        max_tokens=8000)
    data = _parse_files(raw)
    if not data or not isinstance(data.get("files"), dict):
        return {"ok": False, "error": "no files"}
    repo = os.environ["GITHUB_REPOSITORY"]
    for rel, content in data["files"].items():
        await _gh_put(repo, f"{target_dir}/{rel}", content,
                      f"boat: write {target_dir}/{rel}")
    return {"ok": True, "dir": target_dir,
            "files": list(data["files"].keys())}


# ==================================================================
# Projects
# ==================================================================
@tool("projects.create",
      "Start a multi-day project.",
      {"type": "object", "properties": {
          "title": {"type": "string"}, "goal": {"type": "string"},
          "plan": {"type": "array", "items": {"type": "string"}},
      }, "required": ["title", "goal"]}, danger="low")
async def projects_create(title, goal, plan=None, **_i):
    m = _db()
    pid = uuid.uuid4().hex[:8]
    now = time.time()
    m.db.execute(
        "INSERT INTO projects(id,title,goal,status,stage,plan,done,"
        "blocked,notes,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (pid, title, goal, "active", "not_started",
         json.dumps(plan or []), json.dumps([]), json.dumps([]),
         "", now, now))
    m.db.commit()
    return {"ok": True, "project_id": pid, "title": title}


@tool("projects.list", "List projects.",
      {"type": "object", "properties": {"status": {"type": "string"}}},
      danger="low")
async def projects_list(status="active", **_i):
    m = _db()
    if status == "all":
        rows = m.db.execute(
            "SELECT id,title,status,stage FROM projects "
            "ORDER BY updated DESC").fetchall()
    else:
        rows = m.db.execute(
            "SELECT id,title,status,stage FROM projects "
            "WHERE status=? ORDER BY updated DESC", (status,)).fetchall()
    return {"ok": True, "projects": [
        {"id": r[0], "title": r[1], "status": r[2], "stage": r[3]}
        for r in rows]}


@tool("projects.get", "Get full project state.",
      {"type": "object", "properties": {"project_id": {"type": "string"}},
       "required": ["project_id"]}, danger="low")
async def projects_get(project_id, **_i):
    m = _db()
    row = m.db.execute(
        "SELECT id,title,goal,status,stage,plan,done,blocked,notes "
        "FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        return {"ok": False, "reason": "not found"}
    return {"ok": True, "id": row[0], "title": row[1], "goal": row[2],
            "status": row[3], "stage": row[4],
            "plan": json.loads(row[5] or "[]"),
            "done": json.loads(row[6] or "[]"),
            "blocked": json.loads(row[7] or "[]"),
            "notes": row[8]}


@tool("projects.advance", "Mark progress on a project.",
      {"type": "object", "properties": {
          "project_id": {"type": "string"},
          "done_item": {"type": "string"},
          "stage": {"type": "string"},
          "notes": {"type": "string"},
          "blocked_item": {"type": "string"},
      }, "required": ["project_id"]}, danger="low")
async def projects_advance(project_id, done_item="", stage="",
                           notes="", blocked_item="", **_i):
    m = _db()
    row = m.db.execute(
        "SELECT done,blocked,notes,stage FROM projects WHERE id=?",
        (project_id,)).fetchone()
    if not row:
        return {"ok": False, "reason": "not found"}
    done = json.loads(row[0] or "[]")
    blocked = json.loads(row[1] or "[]")
    cur_notes = row[2] or ""
    cur_stage = row[3] or ""
    if done_item:
        done.append({"item": done_item, "at": time.time()})
    if blocked_item:
        blocked.append({"item": blocked_item, "at": time.time()})
    if notes:
        cur_notes = (cur_notes + "\n" + notes).strip()[-2000:]
    if stage:
        cur_stage = stage
    m.db.execute("UPDATE projects SET done=?,blocked=?,notes=?,stage=?,"
                 "updated=? WHERE id=?",
                 (json.dumps(done), json.dumps(blocked), cur_notes,
                  cur_stage, time.time(), project_id))
    m.db.commit()
    return {"ok": True, "stage": cur_stage, "done_count": len(done)}


# ==================================================================
# Research
# ==================================================================
@tool("research.find_clients",
      "Find potential clients. Region 'uganda' or 'worldwide'.",
      {"type": "object", "properties": {
          "niche": {"type": "string"},
          "region": {"type": "string"},
          "count": {"type": "integer", "default": 20},
      }, "required": ["niche"]}, danger="medium")
async def find_clients(niche, region="uganda", count=20, **_i):
    where = ("Uganda, particularly Kampala"
             if region.lower() == "uganda" else "anywhere on the internet")
    prompt = f"""Find {count} real businesses/people that match this niche:
"{niche}"
Location: {where}

For each, provide a plausible contact method.
Return ONLY JSON:
{{"leads": [{{"name": "..","contact": "..","channel": "email|whatsapp|site",
  "region": "{region}","why":"why they might pay","pitch":"40-word pitch"}}]}}
"""
    raw = await _llm(prompt, max_tokens=4000)
    d = _parse_files(raw) or {}
    leads = d.get("leads") or []
    m = _db()
    saved = 0
    for l in leads:
        try:
            m.db.execute(
                "INSERT INTO leads(name,contact,channel,region,pitch,"
                "status,created,updated) VALUES(?,?,?,?,?,?,?,?)",
                (l.get("name", ""), l.get("contact", ""),
                 l.get("channel", "email"), region,
                 l.get("pitch", ""), "new", time.time(), time.time()))
            saved += 1
        except Exception:
            pass
    m.db.commit()
    return {"ok": True, "saved": saved, "leads": leads[:10]}


@tool("research.list_leads", "List saved leads.",
      {"type": "object", "properties": {"status": {"type": "string"}}},
      danger="low")
async def list_leads(status="new", **_i):
    m = _db()
    if status == "all":
        rows = m.db.execute(
            "SELECT id,name,contact,channel,status FROM leads "
            "ORDER BY created DESC").fetchall()
    else:
        rows = m.db.execute(
            "SELECT id,name,contact,channel,status FROM leads "
            "WHERE status=? ORDER BY created DESC", (status,)).fetchall()
    return {"ok": True, "leads": [
        {"id": r[0], "name": r[1], "contact": r[2],
         "channel": r[3], "status": r[4]} for r in rows]}


# ==================================================================
# Meta
# ==================================================================
@tool("meta.evolve",
      "Reflect after a mission. Store a lesson.",
      {"type": "object", "properties": {
          "mission_id": {"type": "string"},
          "outcome": {"type": "string"},
          "trace": {"type": "string"},
      }, "required": ["outcome"]}, danger="low")
async def evolve(mission_id="", outcome="done", trace="", **_i):
    try:
        from .memory import Memory
        memo = Memory()
        memo.add_lesson(mission_id, f"evolve:{outcome}",
                        (trace or "")[:400])
        return {"ok": True, "learned": "lesson"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

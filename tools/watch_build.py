#!/usr/bin/env python3
"""Live DuckWalk build status page.

Polls a GitHub Actions run and rewrites a self-refreshing HTML page the user
can open on their phone to watch build progress without a browser session.

Usage: watch_build.py <run-id> <version> <whats-new, bullets separated by '|'>
"""
import json
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

REPO = "Headspce/duck-walk"
OUT = "/home/hatch/workspace/your_files/duckwalk-build.html"
POLL_SECS = 60
GIVE_UP_SECS = 45 * 60
TYPICAL = "about 9 minutes"
CDT = ZoneInfo("America/Chicago")

RECENT = [
    ("v1.3.0", "Textured duck, blue sky, smooth movement",
     "https://github.com/Headspce/duck-walk/releases/download/v1.3.0/DuckWalk.apk"),
    ("v1.2.0", "Real walk animation, visible duck and ground",
     "https://github.com/Headspce/duck-walk/releases/download/v1.2.0/DuckWalk.apk"),
    ("v1.1.0", "Touch controls, camera fix",
     "https://github.com/Headspce/duck-walk/releases/download/v1.1.0/DuckWalk.apk"),
]


def gh(*args):
    p = subprocess.run(["gh", *args, "--repo", REPO],
                       capture_output=True, text=True, timeout=60)
    return p.stdout.strip()


def run_state(run_id):
    try:
        info = json.loads(gh("run", "view", run_id, "--json",
                             "status,conclusion") or "{}")
        jobs = json.loads(gh("run", "view", run_id, "--json", "jobs") or "{}")
    except Exception:
        return None
    steps = [s for j in jobs.get("jobs", []) for s in j.get("steps", [])]
    done = sum(1 for s in steps if s.get("status") == "completed")
    total = len(steps) or 1
    cur = next((s.get("name", "") for s in steps
                if s.get("status") == "in_progress"), "")
    return {"status": info.get("status", "?"),
            "conclusion": info.get("conclusion") or "",
            "done": done, "total": total, "cur": cur}


def fmt_elapsed(secs):
    m, s = divmod(int(secs), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"


def page(run_id, version, bullets, st, elapsed, note=""):
    if st is None:
        headline, emoji = "Checking build status&hellip;", "\u23f3"
        pct, step_line = 0, "Contacting GitHub&hellip;"
    else:
        status, concl = st["status"], st["conclusion"]
        pct = round(100 * st["done"] / st["total"])
        if status == "completed" and concl == "success":
            headline, emoji = "Build succeeded", "\u2705"
            step_line = (f'<a class="dl" href="https://github.com/Headspce/duck-walk'
                         f'/releases/download/{version}/DuckWalk.apk">'
                         f'Download DuckWalk {version}</a>')
        elif status == "completed":
            headline, emoji = f"Build {concl or 'finished'}", "\u274c"
            step_line = "Wren has been notified and will take a look."
        elif status == "queued":
            headline, emoji = "Queued", "\u23f3"
            step_line = "Waiting for a build machine&hellip;"
        else:
            headline, emoji = "Building", "\U0001f528"
            cur = st["cur"] or "wrapping up"
            step_line = (f"Step {st['done'] + 1} of {st['total']} &middot; "
                         f"<b>{cur}</b>")
    bullets_html = "".join(f"<li>{b.strip()}</li>" for b in bullets if b.strip())
    recent_html = "".join(
        f'<li><a href="{url}">{ver}</a> &mdash; {desc}</li>'
        for ver, desc, url in RECENT)
    updated = datetime.now(CDT).strftime("%-I:%M:%S %p CDT")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="30">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DuckWalk {version} build status</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;
margin:0;padding:24px 18px;max-width:640px}}
h1{{font-size:1.5em;margin:0 0 4px}}h2{{font-size:1.05em;color:#94a3b8;margin:22px 0 8px}}
.status{{font-size:1.25em;font-weight:700;margin:10px 0}}
.bar{{background:#1e293b;border-radius:12px;height:26px;overflow:hidden;margin:12px 0}}
.fill{{background:linear-gradient(90deg,#f59e0b,#fbbf24);height:100%;border-radius:12px;
transition:width 1s}}
.meta{{color:#94a3b8}}ul{{padding-left:20px}}li{{margin:6px 0}}
a{{color:#7dd3fc}}.dl{{display:inline-block;background:#f59e0b;color:#0f172a;font-weight:700;
padding:12px 20px;border-radius:10px;text-decoration:none;margin-top:6px}}
.updated{{color:#64748b;font-size:.85em;margin-top:24px}}
.note{{color:#fbbf24}}
</style></head><body>
<h1>\U0001f986 DuckWalk {version}</h1>
<p class="status">{emoji} {headline}</p>
<div class="bar"><div class="fill" style="width:{pct}%"></div></div>
<p class="meta">{pct}% &middot; {step_line}</p>
<p class="meta">Elapsed {fmt_elapsed(elapsed)} &middot; typical build {TYPICAL}</p>
{f'<p class="note">{note}</p>' if note else ''}
<h2>What's in this build</h2><ul>{bullets_html}</ul>
<h2>Recent releases</h2><ul>{recent_html}</ul>
<p class="updated">Updated {updated} &middot; this page refreshes itself every 30 seconds</p>
</body></html>"""


def main():
    run_id, version = sys.argv[1], sys.argv[2]
    bullets = sys.argv[3].split("|") if len(sys.argv) > 3 else []
    start = time.time()
    last = None
    while True:
        st = run_state(run_id)
        if st is not None:
            last = st
        elapsed = time.time() - start
        finished = last and last["status"] == "completed"
        note = ""
        if not finished and elapsed > GIVE_UP_SECS:
            note = "Stopped auto-checking after 45 minutes; Wren will report the result."
            finished = True
        with open(OUT, "w") as f:
            f.write(page(run_id, version, bullets, last, elapsed, note))
        if finished:
            break
        time.sleep(POLL_SECS)


if __name__ == "__main__":
    main()

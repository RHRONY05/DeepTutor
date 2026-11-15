# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Create (or refresh) the DSA practice course through the running DeepTutor API.

Reads the pattern sheet from ``data/user/dsa/am300.json`` (titles and links only) and makes:

- a course workspace named "DSA" with the DSA course instructions,
- the "dsa-mentor" persona, set as the course's default persona,
- one group per pattern ("01 · Arrays" ...) whose topics are its problems, plus
  "00 · Before you start",
- ``dsa/am300-roadmap.md`` in the course folder.

Safe to run again: existing groups keep their progress (topics are only filled on creation).

    .venv/Scripts/python scripts/fork/setup_dsa_course.py [--api http://127.0.0.1:8001]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "deeptutor" / "services" / "course" / "templates"
DATA = ROOT / "data" / "user" / "dsa"
COURSE_NAME = "DSA"
PERSONA = "dsa-mentor"


def call(api: str, method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        api + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"_status": 404}
        raise SystemExit(f"{method} {path} failed: {exc.code} {exc.read().decode()[:300]}")
    return json.loads(raw) if raw else {}


def group_syllabus(pattern: dict) -> str:
    lines = [f"DSA pattern, phase {pattern['phase']} of the AM-300 roadmap.", "", "## Read first"]
    if pattern["read_first"]:
        lines += [f"- [{r['title']}]({r['url']})" for r in pattern["read_first"]]
    else:
        lines.append("- Nothing new: the lessons from earlier patterns cover it.")
    if pattern.get("video"):
        lines.append(f"- Video intro: {pattern['video']}")
    lines += [
        "",
        "## Problems",
        "",
        "| # | Problem | Difficulty | Solve | Lesson |",
        "|---|---|---|---|---|",
    ]
    for i, p in enumerate(pattern["problems"], 1):
        lines.append(
            f"| {i} | {p['title']} | {p['difficulty']} | [LeetCode]({p['leetcode']}) | [Lesson]({p['lesson']}) |"
        )
    return "\n".join(lines) + "\n"


def start_syllabus(items: list[dict]) -> str:
    lines = [
        "Week 1, light: how interviews work, how to pick a pattern, Big-O, and the C++ you need.",
        "",
        "## Lessons",
    ]
    lines += [f"- [{r['title']}]({r['url']})" for r in items]
    return "\n".join(lines) + "\n"


def group_specs(sheet: dict) -> list[dict]:
    """One spec per group: name, syllabus, lessons [{title, url}], topics with links."""
    start = sheet["before_you_start"]
    specs = [
        {
            "name": "00 · Before you start",
            "syllabus": start_syllabus(start),
            "lessons": [{"title": r["title"], "url": r["url"]} for r in start],
            "topics": [
                {
                    "title": r["title"],
                    "status": "todo",
                    "links": [{"label": "Lesson", "url": r["url"]}],
                }
                for r in start
            ],
        }
    ]
    for i, pattern in enumerate(sheet["patterns"], 1):
        lessons = [{"title": r["title"], "url": r["url"]} for r in pattern["read_first"]]
        if pattern.get("video"):
            lessons.append({"title": "Video intro (YouTube)", "url": pattern["video"]})
        specs.append(
            {
                "name": f"{i:02d} · {pattern['name']}",
                "syllabus": group_syllabus(pattern),
                "lessons": lessons,
                "topics": [
                    {
                        "title": f"{p['title']} ({p['difficulty']})",
                        "status": "todo",
                        "links": [
                            {"label": "LeetCode", "url": p["leetcode"]},
                            {"label": "Lesson", "url": p["lesson"]},
                        ],
                    }
                    for p in pattern["problems"]
                ],
            }
        )
    return specs


def keep_progress(topics: list[dict], old_topics: list[dict]) -> list[dict]:
    """Fresh topics (titles, links) with the statuses already recorded."""
    status = {str(t.get("title", "")).lower(): t.get("status") for t in old_topics}
    return [{**t, "status": status.get(t["title"].lower()) or t["status"]} for t in topics]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://127.0.0.1:8001")
    args = parser.parse_args()
    api = args.api.rstrip("/")

    sheet_file = DATA / "am300.json"
    if not sheet_file.exists():
        print(f"Missing {sheet_file}. Generate the sheet data first.", file=sys.stderr)
        return 1
    sheet = json.loads(sheet_file.read_text(encoding="utf-8"))
    instructions = (TEMPLATES / "dsa_instructions.md").read_text(encoding="utf-8").strip()

    # 1. Course workspace
    rows = call(api, "GET", "/api/settings/workspace/registrations")["workspaces"]
    course = next(
        (
            w
            for w in rows
            if w["kind"] == "workspace" and w["display_name"] == COURSE_NAME and not w["archived"]
        ),
        None,
    )
    if course is None:
        course = call(
            api,
            "POST",
            "/api/settings/workspace/registrations",
            {"name": COURSE_NAME, "instructions": instructions},
        )["workspace"]
        print(f"Created course {COURSE_NAME} ({course['workspace_id']})")
    else:
        call(
            api,
            "PATCH",
            f"/api/settings/workspace/registrations/{course['workspace_id']}",
            {"instructions": instructions},
        )
        print(f"Updated instructions of {COURSE_NAME} ({course['workspace_id']})")
    ws = course["workspace_id"]

    # 2. Persona + course default
    content = (TEMPLATES / "dsa_mentor_persona.md").read_text(encoding="utf-8")
    persona = {
        "name": PERSONA,
        "description": "Senior engineer who coaches DSA with hints first, ideas before code, and step-by-step dry runs",
        "content": content,
    }
    if call(api, "GET", f"/api/personas/{PERSONA}").get("_status") == 404:
        call(api, "POST", "/api/personas", persona)
        print(f"Created persona {PERSONA}")
    else:
        call(
            api,
            "PUT",
            f"/api/personas/{PERSONA}",
            {"description": persona["description"], "content": content},
        )
        print(f"Updated persona {PERSONA}")
    call(api, "PUT", f"/api/courses/{ws}/settings", {"default_persona": PERSONA})

    # 3. Pattern groups (practice type: reading list + problems with links)
    existing = {g["name"]: g for g in call(api, "GET", f"/api/courses/{ws}/groups")["groups"]}
    created = updated = 0
    for spec in group_specs(sheet):
        old = existing.get(spec["name"])
        if old is None:
            old = call(
                api,
                "POST",
                f"/api/courses/{ws}/groups",
                {
                    "name": spec["name"],
                    "type": "practice",
                    "date": "",
                    "syllabus": spec["syllabus"],
                },
            )["group"]
            created += 1
        else:
            updated += 1
        call(
            api,
            "PATCH",
            f"/api/courses/{ws}/groups/{urllib.parse.quote(old['slug'])}",
            {
                "type": "practice",
                "syllabus": spec["syllabus"],
                "lessons": spec["lessons"],
                "topics": keep_progress(spec["topics"], old.get("topics") or []),
            },
        )
    print(f"Groups: {created} created, {updated} refreshed (progress kept)")

    # 4. Roadmap file in the course folder
    roadmap = DATA / "am300-roadmap.md"
    if roadmap.exists():
        target = Path(course["path"]) / "dsa" / "am300-roadmap.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(roadmap, target)
        print(f"Copied roadmap to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

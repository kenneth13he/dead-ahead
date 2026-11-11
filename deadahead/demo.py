"""Fake data for previewing the app without a token."""
from datetime import datetime, timedelta, timezone

from . import build


def demo_feed() -> dict:
    now = datetime.now(timezone.utc)
    local = now.astimezone().replace(minute=59, second=0, microsecond=0)

    def at(days, hour=23):
        return build.iso(local.replace(hour=hour) + timedelta(days=days))

    courses = {
        "1": {"code": "MAT137", "name": "Calculus with Proofs", "color": "#4F8EF7"},
        "2": {"code": "CSC108", "name": "Intro to Computer Programming", "color": "#43AA8B"},
        "3": {"code": "PSY100", "name": "Introductory Psychology", "color": "#F25F5C"},
        "4": {"code": "ENG140", "name": "Literature for Our Time", "color": "#F9A03F"},
    }
    raw = [
        ("1", "Problem Set 3", "assignment", -1, 23, dict(missing=True)),
        ("2", "Lab 6", "assignment", 0, 17, {}),
        ("1", "Problem Set 4", "assignment", 1, 23, {}),
        ("3", "Chapter 9 Quiz", "quiz", 2, 12, {}),
        ("2", "Assignment 2: Gym Membership", "assignment", 3, 16, dict(done=True)),
        ("4", "Reading Response 5", "discussion", 5, 23, {}),
        ("3", "Midterm 2", "test", 6, 18, dict(source="syllabus", note="Covers ch. 6–9, EX100")),
        ("1", "Term Test 2", "test", 9, 9, dict(source="syllabus", weight="20%")),
        ("2", "Lab 7", "assignment", 7, 17, {}),
        ("4", "Essay 2 Proposal", "assignment", 10, 23, {}),
        ("1", "Problem Set 5", "assignment", 12, 23, {}),
        ("2", "Assignment 3", "assignment", 15, 16, {}),
        ("3", "Research Participation Credits", "deadline", 18, 23, dict(source="syllabus")),
        ("4", "Essay 2", "assignment", 19, 23, {}),
    ]
    items = []
    for i, (c, title, kind, d, h, extra) in enumerate(raw):
        item = {
            "id": f"demo-{i}", "source": "quercus", "title": title, "kind": kind,
            "test": build.is_test(title, kind), "course": c, "due": at(d, h),
            "url": None, "points": None, "done": False, "missing": False, "late": False,
        }
        item.update(extra)
        items.append(item)
    return build.build_feed(courses, items, now, "https://q.utoronto.ca")

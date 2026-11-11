"""Turn Canvas planner items + syllabus dates into one clean feed for the phone."""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config, crypto
from .canvas import Canvas

FEED_VERSION = 1
SYLLABUS_PLAIN = config.REPO_ROOT / "syllabus" / "syllabus.json"   # gitignored, you + Claude edit this
SYLLABUS_LOCKED = config.REPO_ROOT / "syllabus" / "syllabus.enc"   # committed, encrypted copy

# Real tests only. Weekly quizzes are still deadlines, just not tagged TEST.
TEST_WORDS = re.compile(r"\b(mid-?terms?|exams?|tests?|finals?|term tests?|tt\d)\b", re.I)
NOT_TEST_WORDS = re.compile(r"\b(remarks?|regrades?|conflict|survey|reflection|post-?test|pre-?test|practice|mock|review session|office hours?)\b", re.I)
# Recurring class events that would drown out real deadlines.
NOISE_EVENTS = re.compile(r"\b(lectures?|office hours?|tutorials?|TA|practicals?|seminars?|recitations?|lab sections?|LEC\d+|TUT\d+|PRA\d+)\b", re.I)
KIND_BY_TYPE = {
    "assignment": "assignment", "quiz": "quiz", "discussion_topic": "discussion",
    "calendar_event": "event", "planner_note": "todo", "wiki_page": "reading",
    "assessment_request": "peer review",
}
SKIP_TYPES = {"announcement"}
PALETTE = ["#4F8EF7", "#F25F5C", "#43AA8B", "#F9A03F", "#9B5DE5", "#00BBF9", "#F15BB5", "#8AC926"]


def readable(color: str) -> str:
    """Brighten very dark Canvas course colours so they read on a dark lock screen."""
    import colorsys
    try:
        r, g, b = (int(color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except (ValueError, TypeError):
        return "#8892A6"
    h, l, sat = colorsys.rgb_to_hls(r, g, b)
    if l < 0.58:
        l, sat = 0.62, max(sat, 0.55)
    return "#" + "".join(f"{round(v * 255):02X}" for v in colorsys.hls_to_rgb(h, l, sat))


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        s += "T23:59:00"
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"Date '{s}' needs a timezone offset, e.g. 2026-11-14T23:59:00-05:00")
    return dt


def short_code(s: str) -> str:
    """'MAT137Y1 Y LEC0101' -> 'MAT137' (UofT style); other schools keep their first word."""
    first = (s or "Course").split()[0]
    m = re.match(r"^([A-Z]{3,4}\d{3})[HY]\d", first)
    return m.group(1) if m else first


def is_test(title: str, kind: str) -> bool:
    if kind in ("test", "exam"):
        return True
    return bool(TEST_WORDS.search(title or "")) and not NOT_TEST_WORDS.search(title or "")


def is_noise_event(title: str, kind: str) -> bool:
    """Lectures / office hours / tutorials. Events that are tests (e.g. 'Midterm (EX100)') are kept."""
    return kind == "event" and bool(NOISE_EVENTS.search(title or "")) and not is_test(title, kind)


# ---------------------------------------------------------------- Quercus

def fetch_courses(cv: Canvas) -> dict:
    courses = cv.get_all("courses", {"enrollment_state": "active"})
    try:
        colors = cv.get("users/self/colors").get("custom_colors", {})
    except Exception:
        colors = {}
    out = {}
    for i, c in enumerate(sorted(courses, key=lambda c: c.get("course_code") or "")):
        if c.get("access_restricted_by_date") or "id" not in c:
            continue
        code = short_code(c.get("course_code") or c.get("name"))
        out[str(c["id"])] = {
            "code": code,
            "name": c.get("name") or code,
            "color": readable(colors.get(f"course_{c['id']}") or PALETTE[i % len(PALETTE)]),
        }
    return out


def normalize_planner_item(p: dict, cv: Canvas, courses: dict) -> dict | None:
    ptype = p.get("plannable_type")
    if ptype in SKIP_TYPES:
        return None
    pl = p.get("plannable") or {}
    due = p.get("plannable_date") or pl.get("due_at") or pl.get("todo_date") or pl.get("start_at")
    if not due:
        return None
    subs = p.get("submissions") or {}
    override = p.get("planner_override") or {}
    title = pl.get("title") or pl.get("name") or "Untitled"
    kind = KIND_BY_TYPE.get(ptype, ptype or "item")
    if is_noise_event(title, kind):
        return None
    course_id = str(p.get("course_id") or "")
    if course_id and course_id not in courses:
        courses[course_id] = {"code": short_code(p.get("context_name")),
                              "name": p.get("context_name") or "Course", "color": "#8892A6"}
    return {
        "id": f"q-{ptype}-{p.get('plannable_id')}",
        "source": "quercus",
        "title": title,
        "kind": kind,
        "test": is_test(title, kind),
        "course": course_id or None,
        "due": iso(parse_dt(due)),
        "url": cv.absolute(p.get("html_url")),
        "points": pl.get("points_possible"),
        "done": bool(subs.get("submitted") or subs.get("excused") or override.get("marked_complete")),
        "missing": bool(subs.get("missing")),
        "late": bool(subs.get("late")),
    }


def fetch_quercus(cv: Canvas, start: datetime, end: datetime) -> tuple[dict, list]:
    courses = fetch_courses(cv)
    raw = cv.get_all("planner/items", {"start_date": iso(start), "end_date": iso(end)})
    items = [i for i in (normalize_planner_item(p, cv, courses) for p in raw) if i]
    return courses, items


# ---------------------------------------------------------------- Syllabus

def load_syllabus(passcode: str | None) -> list:
    if SYLLABUS_PLAIN.exists():
        data = json.loads(SYLLABUS_PLAIN.read_text())
    elif SYLLABUS_LOCKED.exists() and passcode:
        data = crypto.decrypt(json.loads(SYLLABUS_LOCKED.read_text()), passcode)
    else:
        return []
    return data.get("items", data) if isinstance(data, dict) else data


def lock_syllabus(passcode: str) -> Path:
    data = json.loads(SYLLABUS_PLAIN.read_text())
    SYLLABUS_LOCKED.write_text(json.dumps(crypto.encrypt(data, passcode)))
    return SYLLABUS_LOCKED


GENERIC_WORDS = {"quiz", "test", "exam", "final", "assignment", "due", "the", "and", "for", "course",
                 "deadline", "submission", "submit", "tutorial", "lecture"}


def _words(s: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) > 2 or w.isdigit()}


def _same_title(a: str, b: str) -> bool:
    """Share a distinctive word ("Checkpoint Quiz" != "Comprehension Quiz"); all-generic titles fall back to any word."""
    wa, wb = _words(a), _words(b)
    da, db = wa - GENERIC_WORDS, wb - GENERIC_WORDS
    return bool(da & db) if da and db else bool(wa & wb)


def merge_syllabus(items: list, syllabus: list, courses: dict, start: datetime, end: datetime) -> list:
    """Add syllabus dates that Quercus doesn't already have."""
    added = []
    for s in syllabus:
        due = parse_dt(s["due"])
        if not (start <= due <= end):
            continue
        course = str(s.get("course") or "") or "school"
        if course == "school" and "school" not in courses:
            host = config.base_url()
            courses["school"] = {"code": "UofT" if "utoronto" in host else "School",
                                 "name": "School-wide dates", "color": "#8892A6"}
        dup = False
        for q in items:
            if q["course"] != course:
                continue
            close = abs(parse_dt(q["due"]) - due) <= timedelta(days=1)
            if close and _same_title(q["title"], s["title"]):
                dup = True
                break
        if dup:
            continue
        kind = s.get("kind", "deadline")
        added.append({
            "id": f"s-{course}-{due.date()}-{re.sub(r'[^a-z0-9]+', '-', s['title'].lower())[:40]}",
            "source": "syllabus",
            "title": s["title"],
            "kind": kind,
            "test": is_test(s["title"], kind),
            "course": course,
            "due": iso(due),
            "all_day": bool(s.get("all_day")),
            "url": s.get("url"),
            "note": s.get("note"),
            "weight": s.get("weight"),
            "done": False, "missing": False, "late": False,
        })
    return items + added


# ---------------------------------------------------------------- Feed

def build_feed(courses: dict, items: list, now: datetime, base_url: str) -> dict:
    items.sort(key=lambda i: (i["due"], i["title"]))
    return {
        "v": FEED_VERSION,
        "generated_at": iso(now),
        "window_days": config.WINDOW_DAYS,
        "school": base_url,
        "courses": courses,
        "items": items,
    }


def window(now: datetime) -> tuple[datetime, datetime]:
    return now - timedelta(days=config.LOOKBACK_DAYS), now + timedelta(days=config.WINDOW_DAYS)


def run(out_dir: Path) -> dict:
    now = datetime.now(timezone.utc)
    start, end = window(now)
    passcode = config.passcode()
    cv = Canvas(config.base_url(), config.token())
    courses, items = fetch_quercus(cv, start, end)
    items = merge_syllabus(items, load_syllabus(passcode), courses, start, end)
    feed = build_feed(courses, items, now, cv.base_url)
    write_feed(feed, passcode, out_dir)
    return feed


def write_feed(feed: dict, passcode: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "feed.enc.json"
    path.write_text(json.dumps(crypto.encrypt(feed, passcode)))
    return path

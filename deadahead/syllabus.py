"""Download every syllabus-like document from your active courses as plain text.

Output: syllabus/raw/<COURSE>/... .txt + syllabus/raw/index.json (all gitignored).
Then, once per term, Claude Code reads them and writes syllabus/syllabus.json.
"""
import html
import io
import json
import re
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from . import config
from .canvas import _SSL, USER_AGENT, Canvas, CanvasError

RAW_DIR = config.REPO_ROOT / "syllabus" / "raw"
NAME_HINTS = re.compile(
    r"syllab|outline|schedule|calendar|important dates|course info|assessment|evaluation|timeline|"
    r"course website|course materials|course page|deadlines?|due dates|\btests?\b|mid-?terms?|exams?|"
    r"problem sets?|policies", re.I)
SKIP_HINTS = re.compile(r"solution|recording|zoom|slides|worksheet|practice|office hour", re.I)
LINK_RE = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
MAX_DOCS_PER_COURSE = 20
SEARCH_TERMS = ["syllabus", "outline", "schedule", "calendar"]
MAX_BYTES = 25 * 1024 * 1024


def html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s or "")
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h\d)>", "\n", s)
    s = re.sub(r"(?i)</t[dh]>", " | ", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", s)).strip()


GLYPHS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "numbersign": "#", "colon": ":", "hyphen": "-", "endash": "–", "period": ".",
    "comma": ",", "slash": "/", "percent": "%", "parenleft": "(", "parenright": ")", "dollar": "$", "ampersand": "&",
}
GLYPH_RE = re.compile(r"/(" + "|".join(GLYPHS) + r")(?:\.(?:osf|tosf|tf|lf|sups|sinf|onum|lnum|pnum|tnum|sc))+")


def fix_glyph_names(text: str) -> str:
    """Some PDFs (old-style figures) extract digits as '/two.osf'. Turn them back into characters."""
    return GLYPH_RE.sub(lambda m: GLYPHS[m.group(1)], text)


def file_to_text(name: str, data: bytes) -> str | None:
    n = name.lower()
    if n.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text = "\n\n".join(f"--- page {i + 1} ---\n{p.extract_text() or ''}" for i, p in enumerate(reader.pages))
        return fix_glyph_names(text)
    if n.endswith(".docx"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        xml = re.sub(r"</w:p>", "\n", xml)
        xml = re.sub(r"</w:tc>", " | ", xml)
        return html.unescape(re.sub(r"<[^>]+>", "", xml))
    if n.endswith((".html", ".htm")):
        return html_to_text(data.decode("utf-8", "ignore"))
    if n.endswith((".txt", ".md", ".csv")):
        return data.decode("utf-8", "ignore")
    return None


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:80]


def _try(fn, default):
    try:
        return fn()
    except CanvasError:
        return default  # many courses hide Files/Pages from students; that's fine


def _wanted(title: str) -> bool:
    return bool(NAME_HINTS.search(title or "")) and not SKIP_HINTS.search(title or "")


def _enqueue_links(body: str, cv: Canvas, cid: str, queue: list, depth: int):
    """Follow links that look like syllabus material. Canvas links use the token; outside links never do."""
    host = urllib.parse.urlparse(cv.base_url).netloc
    for href, inner in LINK_RE.findall(body or ""):
        href = html.unescape(href)
        label = re.sub(r"<[^>]+>", "", html.unescape(inner)).strip()
        u = urllib.parse.urlparse(urllib.parse.urljoin(cv.base_url + "/", href))
        hint = f"{label} {u.path}"
        if u.netloc == host:
            m = re.search(r"/files/(\d+)", u.path)
            if m and (_wanted(hint) or not label or label.lower() in ("here", "link", "download")):
                queue.append(("file", m.group(1), label or "file", depth))
                continue
            m = re.search(rf"/courses/{cid}/pages/([^/?#]+)", u.path)
            if m and _wanted(hint):
                queue.append(("page", m.group(1), label or m.group(1), depth))
        elif u.scheme in ("http", "https") and _wanted(label):
            queue.append(("web", u.geturl(), label, depth))


def _download_public(url: str) -> tuple[str, bytes]:
    """Fetch an outside page/PDF WITHOUT any credentials."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30, context=_SSL) as r:
        data = r.read(MAX_BYTES)
        ctype = r.headers.get("Content-Type", "")
    path = urllib.parse.urlparse(url).path
    name = path.rsplit("/", 1)[-1] or "index"
    if "pdf" in ctype and not name.lower().endswith(".pdf"):
        name += ".pdf"
    elif "html" in ctype and not name.lower().endswith((".html", ".htm")):
        name += ".html"
    return name, data


def pull(cv: Canvas, log=print) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    index = []
    for c in cv.get_all("courses", {"enrollment_state": "active", "include[]": "syllabus_body"}):
        if "id" not in c or c.get("access_restricted_by_date"):
            continue
        cid = str(c["id"])
        code = (c.get("course_code") or c.get("name") or cid).split()[0]
        folder = RAW_DIR / _safe(code)
        folder.mkdir(exist_ok=True)
        docs = []

        def save(label: str, text: str | None, source: str):
            if text and len(text.strip()) > 80:
                path = folder / f"{_safe(label)}.txt"
                path.write_text(text)
                docs.append({"file": str(path.relative_to(RAW_DIR)), "source": source, "chars": len(text)})

        # 1) Syllabus tab
        save("syllabus_tab", html_to_text(c.get("syllabus_body") or ""), "syllabus tab")

        # 2) Files whose names look like a syllabus (search may be blocked for students; that's OK)
        files = {}
        for term in SEARCH_TERMS:
            for f in _try(lambda: cv.get_all(f"courses/{cid}/files", {"search_term": term}), []):
                files[f["id"]] = f
        # 3) Pages/files/links: module items + front page, then follow links (2 hops)
        queue = []  # (kind, ref, label, depth)
        for m in _try(lambda: cv.get_all(f"courses/{cid}/modules", {"include[]": "items"}), []):
            for it in m.get("items") or []:
                t = it.get("title") or ""
                if not _wanted(t):
                    continue
                if it.get("type") == "File" and it.get("content_id"):
                    queue.append(("file", it["content_id"], t, 1))
                elif it.get("type") == "Page" and it.get("page_url"):
                    queue.append(("page", it["page_url"], t, 1))
                elif it.get("type") == "ExternalUrl" and it.get("external_url"):
                    queue.append(("web", it["external_url"], t, 1))
        for f in files.values():
            queue.append(("file", f["id"], f.get("display_name") or "file", 1))
        _enqueue_links(c.get("syllabus_body") or "", cv, cid, queue, 1)
        front = _try(lambda: cv.get(f"courses/{cid}/front_page"), None)
        if front:
            save(f"page_{front.get('title') or 'home'}", html_to_text(front.get("body") or ""), "home page")
            _enqueue_links(front.get("body") or "", cv, cid, queue, 1)

        seen = set()
        while queue and len(docs) < MAX_DOCS_PER_COURSE:
            kind, ref, label, depth = queue.pop(0)
            if (kind, ref) in seen:
                continue
            seen.add((kind, ref))
            try:
                if kind == "page":
                    page = _try(lambda: cv.get(f"courses/{cid}/pages/{ref}"), None)
                    if not page:
                        continue
                    body = page.get("body") or ""
                    save(f"page_{page.get('title') or label}", html_to_text(body), f"page: {page.get('title') or label}")
                    if depth < 2:
                        _enqueue_links(body, cv, cid, queue, depth + 1)
                elif kind == "file":
                    f = _try(lambda: cv.get(f"files/{ref}"), None)
                    if not f or not f.get("url") or (f.get("size") or 0) > MAX_BYTES:
                        continue
                    name = f.get("display_name") or f.get("filename") or label
                    save(name, file_to_text(name, cv.download(f["url"])), f"file: {name}")
                elif kind == "web":
                    name, data = _download_public(ref)
                    text = file_to_text(name, data)
                    save(f"web_{label}", text, f"website: {ref}")
            except Exception as e:  # unreadable PDF, dead link, etc.
                log(f"  ! {code}: skipped {label[:40]} ({e.__class__.__name__})")

        log(f"  {code}: {len(docs)} document(s)")
        index.append({"course": cid, "code": code, "name": c.get("name"), "docs": docs})

    out = RAW_DIR / "index.json"
    out.write_text(json.dumps(index, indent=2))
    return out

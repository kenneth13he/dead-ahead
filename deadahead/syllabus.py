"""Download every syllabus-like document from your active courses as plain text.

Output: syllabus/raw/<COURSE>/... .txt + syllabus/raw/index.json (all gitignored).
Then, once per term, Claude Code reads them and writes syllabus/syllabus.json.
"""
import html
import io
import json
import re
import zipfile
from pathlib import Path

from . import config
from .canvas import Canvas, CanvasError

RAW_DIR = config.REPO_ROOT / "syllabus" / "raw"
NAME_HINTS = re.compile(r"syllab|outline|schedule|calendar|important dates|course info|assessment|evaluation|timeline", re.I)
SEARCH_TERMS = ["syllabus", "outline", "schedule", "calendar"]
MAX_BYTES = 25 * 1024 * 1024


def html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s or "")
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h\d)>", "\n", s)
    s = re.sub(r"(?i)</t[dh]>", " | ", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", s)).strip()


def file_to_text(name: str, data: bytes) -> str | None:
    n = name.lower()
    if n.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(f"--- page {i + 1} ---\n{p.extract_text() or ''}" for i, p in enumerate(reader.pages))
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

        # 2) Files whose names look like a syllabus (search + module links)
        files = {}
        for term in SEARCH_TERMS:
            for f in _try(lambda: cv.get_all(f"courses/{cid}/files", {"search_term": term}), []):
                files[f["id"]] = f
        modules = _try(lambda: cv.get_all(f"courses/{cid}/modules", {"include[]": "items"}), [])
        pages = {}
        for m in modules:
            for it in m.get("items") or []:
                if not NAME_HINTS.search(it.get("title") or ""):
                    continue
                if it.get("type") == "File" and it.get("content_id") not in files:
                    f = _try(lambda: cv.get(f"files/{it['content_id']}"), None)
                    if f:
                        files[f["id"]] = f
                elif it.get("type") == "Page" and it.get("page_url"):
                    pages[it["page_url"]] = it["title"]
        for p in _try(lambda: cv.get_all(f"courses/{cid}/pages", {"search_term": "syllabus"}), []):
            pages.setdefault(p.get("url"), p.get("title"))

        for f in files.values():
            name = f.get("display_name") or f.get("filename") or "file"
            if (f.get("size") or 0) > MAX_BYTES or not f.get("url"):
                continue
            try:
                text = file_to_text(name, cv.download(f["url"]))
            except Exception as e:  # unreadable PDF etc.
                log(f"  ! {code}: couldn't read {name} ({e.__class__.__name__})")
                continue
            save(name, text, f"file: {name}")

        # 3) Pages
        for url, title in pages.items():
            page = _try(lambda: cv.get(f"courses/{cid}/pages/{url}"), None)
            if page:
                save(f"page_{title}", html_to_text(page.get("body") or ""), f"page: {title}")

        log(f"  {code}: {len(docs)} document(s)")
        index.append({"course": cid, "code": code, "name": c.get("name"), "docs": docs})

    out = RAW_DIR / "index.json"
    out.write_text(json.dumps(index, indent=2))
    return out

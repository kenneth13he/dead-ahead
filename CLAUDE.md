# Dead Ahead: notes for Claude Code

## "Extract my syllabus dates"
When the user asks this (once per term):

1. Make sure `syllabus/raw/index.json` exists. If not, run `python -m deadahead pull-syllabus` (needs
   `~/.config/dead-ahead/token`). **Never** print, read aloud, or ask the user to paste their token.
2. Read every `.txt` listed in `syllabus/raw/index.json`. Each entry has the Canvas course id (`course`) and code.
3. Pull out every **dated** item a student must act on or attend: tests, quizzes, midterms, exams, assignment and
   project deadlines, presentations, labs with due dates, participation/research credit deadlines, drop dates.
   - Resolve "Week 5 Friday" / "Lecture 12" using term start dates and the schedule tables in the same document.
     If you can't resolve a date confidently, leave it out and list it for the user under **"Couldn't date"**.
   - Skip weekly recurring lectures/tutorials and anything already past.
   - Use the school's timezone with an explicit offset (UofT: `America/Toronto` → `-05:00` in winter, `-04:00` in
     summer/early fall). If no time is given, use `23:59` and set `"all_day": true` for exams/events with no time.
   - Quercus deadlines are merged automatically (duplicates within a day sharing title words are dropped), so it's
     fine to include items that may also be on Quercus.
4. Write `syllabus/syllabus.json` (gitignored) in this format:

```json
{
  "term": "Fall 2026",
  "items": [
    {
      "course": "123456",
      "title": "Midterm 2",
      "kind": "test",
      "due": "2026-11-16T18:00:00-05:00",
      "all_day": false,
      "weight": "20%",
      "note": "EX100 · covers ch. 6–9",
      "source": "PSY100/Course_Outline.pdf.txt p.3"
    }
  ]
}
```
   `kind` is one of `test`, `exam`, `deadline`, `assignment`, `event`. Keep titles short (lock-screen space).
5. Show the user a table grouped by course (date, title, weight, source) plus the **Couldn't date** list, and ask them to
   check it. Apply their corrections.
6. Run `python -m deadahead lock-syllabus`, then remind them to commit `syllabus/syllabus.enc` and push.

## Project layout
- `deadahead/`: Python: Canvas client, build/merge, crypto, syllabus puller, CLI (`python -m deadahead …`)
- `site/`: the home-screen web app (static; `feed.enc.json` is generated, never committed)
- `scriptable/Dead Ahead.js`: iPhone lock-screen widget + wallpaper (Scriptable app)
- `tools/`: icon generator, iPhone screenshot helper (`shoot.mjs`), wallpaper preview harness
- Crypto format must stay identical in `deadahead/crypto.py`, `site/app.js` and `scriptable/Dead Ahead.js`.

## Rules
- Secrets live only in `~/.config/dead-ahead/` or GitHub secrets. Never in the repo, logs or chat.
- `syllabus/raw/` and `syllabus/syllabus.json` are personal; never commit them.
- Tests: `python -m unittest discover -s tests -t .`

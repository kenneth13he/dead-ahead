# Dead Ahead ▲

**Your deadlines, straight ahead.** Every Quercus/Canvas deadline *and* every date buried in your syllabi,
on your iPhone's home screen, lock screen and wallpaper. Free, no servers, no app store.

| Home-screen app | Lock-screen widget | Daily wallpaper |
|---|---|---|
| 3-week timeline, countdowns, tests, tap to open in Quercus | Urgent work: the next things due, plus how many are late | Your whole week, tests included, refreshed every morning |

Works with **any Canvas school** (built at UofT, where Canvas is called Quercus).
*Not affiliated with Instructure, Canvas, or the University of Toronto.*

## How it works

```
Canvas API ──(your token: a GitHub secret)──┐
Syllabus dates ──(extracted once per term)──┤
                                            ▼
             GitHub Actions, every 3 hours: fetch the next 21 days
                                            ▼
             encrypt with YOUR passcode → GitHub Pages (free hosting)
                                            ▼
     📱 home-screen app · 🔒 lock-screen widget · 🖼 wallpaper (all decrypt on your phone)
```

Everyone runs **their own copy**. Your token lives only in your GitHub repo's secrets, and your deadlines are
published **encrypted** (AES-256-GCM, PBKDF2 600k), so the public Pages URL shows nothing without your passcode.

---

## Setup (about 15 minutes, needs a computer once)

### 1. Make your copy
Click **Use this template → Create a new repository**. Make it **Public** (GitHub Pages is free for public repos;
your data is encrypted).

### 2. Create a Canvas token
Quercus/Canvas → **Account → Settings → Approved Integrations → + New Access Token**.
Purpose: `Dead Ahead`. Expiry: the end of term. Copy it (you only see it once).

> ⚠️ A Canvas token can do anything your account can. Never paste it into code, chats or issues, only into the
> places below. Revoke it in the same settings page any time.

### 3. Add your secrets on GitHub
In your new repo: **Settings → Secrets and variables → Actions**
- **Secrets → New repository secret**
  - `CANVAS_TOKEN`: the token from step 2
  - `DEADAHEAD_PASSCODE`: a **passphrase** of 12+ characters (e.g. `purple-ferry-salad-42`). You'll type it once on your phone.
- **Variables → New repository variable** (skip if you're at UofT)
  - `CANVAS_BASE_URL`: e.g. `https://canvas.yourschool.edu`

### 4. Turn on Pages and run it
- **Settings → Pages → Source: GitHub Actions**
- **Actions → Update deadlines → Run workflow**
- When it's green, your app is at `https://<your-username>.github.io/<repo-name>/`

### 5. Set up your iPhone
Follow **[SETUP-IPHONE.md](SETUP-IPHONE.md)**: home-screen app, lock-screen widget, daily wallpaper.

---

## Syllabus dates (once per term)

Lots of profs only put midterms and deadlines in the syllabus PDF. Dead Ahead downloads every syllabus-like
document (syllabus tab, files and module links named *syllabus/outline/schedule…*), then you let an AI read them.

On a Mac/PC with this repo cloned:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# store your token + passcode privately (not in the repo)
mkdir -p ~/.config/dead-ahead && chmod 700 ~/.config/dead-ahead
# copy your token, then:
pbpaste > ~/.config/dead-ahead/token && pbcopy < /dev/null    # macOS; or paste it into that file by hand
read -rs "?Passcode: " P && printf %s "$P" > ~/.config/dead-ahead/passcode; unset P   # zsh
chmod 600 ~/.config/dead-ahead/*
# not at UofT?  echo https://canvas.yourschool.edu > ~/.config/dead-ahead/base_url

python -m deadahead check            # ✓ Connected … lists your courses
python -m deadahead pull-syllabus    # downloads syllabi as text into syllabus/raw/ (never committed)
```

Then open **[Claude Code](https://claude.com/claude-code)** in the repo and say:

> **Extract my syllabus dates**

[CLAUDE.md](CLAUDE.md) tells it exactly what to do: it reads `syllabus/raw/`, writes `syllabus/syllabus.json`,
and shows you the list to check. Then:

```bash
python -m deadahead lock-syllabus    # encrypts → syllabus/syllabus.enc (safe to commit)
git add syllabus/syllabus.enc && git commit -m "Syllabus dates for this term" && git push
```

No AI? Write `syllabus/syllabus.json` by hand. The format is in [CLAUDE.md](CLAUDE.md).

---

## Commands

| Command | What it does |
|---|---|
| `python -m deadahead check` | Tests your token, lists courses |
| `python -m deadahead build` | Fetches + encrypts → `site/feed.enc.json` |
| `python -m deadahead pull-syllabus` | Downloads syllabi as text into `syllabus/raw/` |
| `python -m deadahead lock-syllabus` | Encrypts `syllabus.json` → `syllabus.enc` |
| `python -m deadahead demo` | Fake data for previewing (passcode `demo-passcode`) |
| `python -m unittest discover -s tests -t .` | Run tests |

## Good to know
- **Updates every 3 hours.** Tap ↻ in the app for the latest published copy.
- **GitHub pauses scheduled runs** in repos with no activity for 60 days. If your app says "not refreshing",
  go to **Actions → Update deadlines → Enable workflow**. Committing your syllabus each term keeps it alive.
- **Token expired?** Make a new one and update the `CANVAS_TOKEN` secret.
- **Changed your passcode?** Update the secret, re-run `lock-syllabus`, and re-enter it on your phone.
- Ticking ✓ in the app only hides an item on that phone. It doesn't submit anything to Canvas.

## License
MIT. Free to use, share and remix.

"""Dead Ahead command line.

  python -m deadahead check            test your token (prints course list, no deadlines)
  python -m deadahead build            fetch Quercus + syllabus -> site/feed.enc.json
  python -m deadahead pull-syllabus    download syllabi as text into syllabus/raw/
  python -m deadahead lock-syllabus    encrypt syllabus/syllabus.json -> syllabus.enc (safe to commit)
  python -m deadahead demo             write a fake feed so you can preview the app
"""
import argparse
import sys
from pathlib import Path

from . import build, config
from .canvas import Canvas, CanvasError


def main(argv=None):
    ap = argparse.ArgumentParser(prog="deadahead", description="Dead Ahead: your deadlines, straight ahead.")
    ap.add_argument("command", choices=["check", "build", "pull-syllabus", "lock-syllabus", "demo"])
    ap.add_argument("--out", default=str(config.REPO_ROOT / "site"), help="where feed.enc.json goes")
    args = ap.parse_args(argv)

    try:
        if args.command == "check":
            cv = Canvas(config.base_url(), config.token())
            me = cv.get("users/self")
            courses = build.fetch_courses(cv)
            print(f"✓ Connected to {cv.base_url} as {me.get('short_name') or me.get('name')}")
            print(f"✓ {len(courses)} active course(s): " + ", ".join(c["code"] for c in courses.values()))
        elif args.command == "build":
            feed = build.run(Path(args.out))
            n_syl = sum(1 for i in feed["items"] if i["source"] == "syllabus")
            print(f"✓ {len(feed['items'])} item(s) ({n_syl} from syllabi) -> {args.out}/feed.enc.json")
        elif args.command == "pull-syllabus":
            from . import syllabus
            cv = Canvas(config.base_url(), config.token())
            print("Pulling syllabi…")
            print(f"✓ Index: {syllabus.pull(cv)}")
        elif args.command == "lock-syllabus":
            print(f"✓ Encrypted -> {build.lock_syllabus(config.passcode())}")
        elif args.command == "demo":
            from .demo import demo_feed
            path = build.write_feed(demo_feed(), "demo-passcode", Path(args.out))
            print(f"✓ Demo feed -> {path}  (passcode: demo-passcode)")
    except (config.ConfigError, CanvasError, ValueError) as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

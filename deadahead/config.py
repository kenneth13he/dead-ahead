"""Settings come from environment variables first (GitHub Actions), then from
private files in ~/.config/dead-ahead/ (your Mac). Secrets never live in the repo."""
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("DEADAHEAD_CONFIG_DIR", Path.home() / ".config" / "dead-ahead"))
REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_BASE_URL = "https://q.utoronto.ca"  # Quercus. Any Canvas school works.
WINDOW_DAYS = 21       # how far ahead to look
LOOKBACK_DAYS = 3      # keep recently-overdue items visible


class ConfigError(RuntimeError):
    pass


def _secret(env_name: str, file_name: str, required: bool = True) -> str | None:
    value = os.environ.get(env_name)
    if value:
        return value.strip()
    path = CONFIG_DIR / file_name
    if path.exists():
        value = path.read_text().strip()
        if value:
            return value
    if required:
        raise ConfigError(
            f"Missing {env_name}. Set the environment variable or put it in {path} "
            f"(see README → 'Syllabus dates')."
        )
    return None


def base_url() -> str:
    url = os.environ.get("CANVAS_BASE_URL") or _secret("CANVAS_BASE_URL", "base_url", required=False)
    return (url or DEFAULT_BASE_URL).rstrip("/")


def token() -> str:
    return _secret("CANVAS_TOKEN", "token")


def passcode() -> str:
    code = _secret("DEADAHEAD_PASSCODE", "passcode")
    if len(code) < 8:
        raise ConfigError("Passcode must be at least 8 characters. Use a passphrase, not a PIN.")
    return code

"""Tiny Canvas LMS REST client (standard library only)."""
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "DeadAhead/1.0 (+self-hosted deadline viewer)"

try:  # python.org builds on macOS ship without CA certificates; certifi fixes that everywhere
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL = ssl.create_default_context()


class CanvasError(RuntimeError):
    pass


class Canvas:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self._token = token

    def _request(self, url: str, raw: bool = False):
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        })
        try:
            resp = urllib.request.urlopen(req, timeout=60, context=_SSL)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise CanvasError("Canvas rejected the token (401). It may be expired or revoked.") from None
            raise CanvasError(f"Canvas returned HTTP {e.code} for {url.split('?')[0]}") from None
        except urllib.error.URLError as e:
            raise CanvasError(f"Could not reach Canvas: {e.reason}") from None
        with resp:
            body = resp.read()
            link = resp.headers.get("Link", "")
        if raw:
            return body, link
        return json.loads(body), link

    def get(self, path: str, params: dict | list | None = None):
        url = f"{self.base_url}/api/v1/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        data, _ = self._request(url)
        return data

    def get_all(self, path: str, params: dict | list | None = None, max_pages: int = 50) -> list:
        """Follows Canvas' Link: <...>; rel="next" pagination."""
        params = list(params.items()) if isinstance(params, dict) else list(params or [])
        params.append(("per_page", 100))
        url = f"{self.base_url}/api/v1/{path.lstrip('/')}?" + urllib.parse.urlencode(params, doseq=True)
        out = []
        for _ in range(max_pages):
            data, link = self._request(url)
            out.extend(data)
            nxt = re.search(r'<([^>]+)>;\s*rel="next"', link)
            if not nxt:
                break
            url = nxt.group(1)
        return out

    def download(self, url: str) -> bytes:
        body, _ = self._request(url, raw=True)
        return body

    def absolute(self, path: str | None) -> str | None:
        if not path:
            return None
        return path if path.startswith("http") else self.base_url + path

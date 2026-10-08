#!/usr/bin/env python3
"""Small App Store Connect API client used by the other scripts in this skill.

Needs Python 3.9+ and `pip install pyjwt cryptography`. Runs on macOS, Windows and Linux.

Credentials, first match wins:
  1. Environment: ASC_KEY_ID, ASC_ISSUER_ID, and ASC_PRIVATE_KEY_PATH (a .p8 file) or
     ASC_PRIVATE_KEY (the .p8 contents, for CI secrets).
  2. A profile file: ~/.config/appstoreconnect/<profile>.env with the same names.
     The profile is --profile, else $ASC_PROFILE, else "credentials".
One profile per Apple team: a key only sees the apps of the team that issued it.

As a command:
  python asc_api.py apps
  python asc_api.py GET "/v1/apps/123/appStoreVersions?limit=5"
  python asc_api.py PATCH /v1/appStoreVersions/abc @body.json
  python asc_api.py --profile clientteam GET /v1/apps
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.appstoreconnect.apple.com"
CONFIG_DIR = Path.home() / ".config" / "appstoreconnect"
RETRY_STATUS = {429, 500, 502, 503, 504}


class ApiError(Exception):
    """An HTTP error from the API. `codes` includes the nested meta.associatedErrors codes."""

    def __init__(self, method, path, status, body):
        self.method, self.path, self.status, self.body = method, path, status, body
        self.errors = body.get("errors", []) if isinstance(body, dict) else []
        self.codes = []
        for e in self.errors:
            self.codes.append(e.get("code", ""))
            for group in ((e.get("meta") or {}).get("associatedErrors") or {}).values():
                self.codes.extend(x.get("code", "") for x in group)
        super().__init__(self.describe())

    def describe(self):
        lines = [f"HTTP {self.status} on {self.method} {self.path}"]
        for e in self.errors:
            lines.append(f"  [{e.get('code')}] {e.get('title')}: {e.get('detail')}")
            # The real reason for a 409 on submission is often only here.
            for target, group in ((e.get("meta") or {}).get("associatedErrors") or {}).items():
                for x in group:
                    lines.append(f"    {target}: [{x.get('code')}] {x.get('detail')}")
        if not self.errors:
            lines.append("  " + json.dumps(self.body)[:400])
        return "\n".join(lines)

    def has(self, fragment):
        return any(fragment in c for c in self.codes) or fragment in json.dumps(self.body)

    @property
    def agreement_blocked(self):
        """The account holder has an agreement to accept, or the membership has lapsed."""
        return self.has("DPLA_OUTDATED") or (self.status == 403 and "agreement" in json.dumps(self.body).lower())


def normalize_path(path):
    """Git Bash on Windows rewrites a leading /v1/... argument into C:/Program Files/Git/v1/..."""
    m = re.search(r"/v\d+/", path)
    return path[m.start():] if m and not path.startswith("/v") else path


def load_credentials(profile=None):
    env = {}
    name = profile or os.environ.get("ASC_PROFILE") or "credentials"
    f = CONFIG_DIR / f"{name}.env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    elif profile:
        sys.exit(f"credentials profile not found: {f}")
    for k in ("ASC_KEY_ID", "ASC_ISSUER_ID", "ASC_PRIVATE_KEY_PATH", "ASC_PRIVATE_KEY"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    if not env.get("ASC_KEY_ID") or not (env.get("ASC_PRIVATE_KEY_PATH") or env.get("ASC_PRIVATE_KEY")):
        sys.exit("App Store Connect credentials missing. Set ASC_KEY_ID, ASC_ISSUER_ID and ASC_PRIVATE_KEY_PATH,\n"
                 f"or write them to {f}. See references/setup.md.")
    return env


class Api:
    def __init__(self, profile=None):
        self.env = load_credentials(profile)
        self._token, self._token_until = None, 0

    def token(self):
        import jwt  # imported here so --help works without it
        now = int(time.time())
        if self._token and now < self._token_until:
            return self._token
        key = self.env.get("ASC_PRIVATE_KEY") or Path(os.path.expanduser(self.env["ASC_PRIVATE_KEY_PATH"])).read_text(encoding="utf-8")
        claims = {"iat": now, "exp": now + 1000, "aud": "appstoreconnect-v1"}
        if self.env.get("ASC_ISSUER_ID"):
            claims["iss"] = self.env["ASC_ISSUER_ID"]
        else:
            claims["sub"] = "user"  # individual API keys have no issuer
        self._token = jwt.encode(claims, key, algorithm="ES256", headers={"kid": self.env["ASC_KEY_ID"], "typ": "JWT"})
        self._token_until = now + 900
        return self._token

    def request(self, method, path, body=None):
        path = normalize_path(path)
        url = path if path.startswith("http") else BASE + path
        data = json.dumps(body).encode() if body is not None else None
        attempts = 4 if method == "GET" else 1  # writes are never retried blindly
        for attempt in range(attempts):
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("Authorization", "Bearer " + self.token())
            if data is not None:
                req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    raw = r.read()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                raw = e.read()
                if e.code in RETRY_STATUS and attempt < attempts - 1:
                    time.sleep(3 * (attempt + 1))
                    continue
                try:
                    parsed = json.loads(raw or b"{}")
                except ValueError:
                    parsed = {"errors": [{"code": "NON_JSON", "title": "non-JSON error body", "detail": raw.decode(errors="replace")[:300]}]}
                raise ApiError(method, path, e.code, parsed) from None
            except urllib.error.URLError:
                if attempt < attempts - 1:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, body):
        return self.request("POST", path, body)

    def patch(self, path, body):
        return self.request("PATCH", path, body)

    def delete(self, path):
        return self.request("DELETE", path)

    def get_all(self, path, cap=2000):
        """Follow links.next and return every item in `data`."""
        out = []
        while path:
            d = self.get(path)
            out.extend(d.get("data", []))
            path = (d.get("links") or {}).get("next")
            if len(out) >= cap:
                break
        return out


def main(argv):
    profile = None
    if argv[:1] == ["--profile"]:
        profile, argv = argv[1], argv[2:]
    if not argv or argv[0] in ("-h", "--help"):
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")
    api = Api(profile)
    try:
        if argv[0] == "apps":
            for a in api.get_all("/v1/apps?fields[apps]=name,bundleId,sku&limit=200"):
                t = a["attributes"]
                print(f"{a['id']:<12} {t['bundleId']:<40} {t['name']}")
            return
        method, path = argv[0].upper(), argv[1]
        body = None
        if len(argv) > 2:
            body = json.loads(Path(argv[2][1:]).read_text(encoding="utf-8") if argv[2].startswith("@") else argv[2])
        print(json.dumps(api.request(method, path, body), indent=1))
    except ApiError as e:
        sys.exit(e.describe())


if __name__ == "__main__":
    main(sys.argv[1:])

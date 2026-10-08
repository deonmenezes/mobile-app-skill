#!/usr/bin/env python3
"""Download App Store provisioning profiles by name, so a build host needs no profile files of its own.

  python fetch_profiles.py --out profiles "My App AppStore" "My App Widget AppStore"
  python fetch_profiles.py --list                 every profile the key can see, with its team and bundle id
  python fetch_profiles.py --profile clientteam --out profiles "Client App AppStore"

Each profile is saved as <uuid>.mobileprovision, the file name Xcode expects. Copy them into BOTH
  ~/Library/Developer/Xcode/UserData/Provisioning Profiles/   (Xcode 16 and later)
  ~/Library/MobileDevice/Provisioning Profiles/               (older Xcode)
mac_release.sh does that when PROFILE_DIR points at the folder.

A profile is a snapshot: after changing an App ID's capabilities or App Groups, regenerate the profile in the
developer portal and fetch it again. The check below prints the App Groups each profile really carries.
Exit codes: 0 ok, 2 a named profile was not found or is not active, 4 API error.
"""
import base64
import plistlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from asc_api import Api, ApiError  # noqa: E402


def embedded_plist(raw):
    """The plist inside the CMS-signed profile."""
    m = re.search(rb"<\?xml.*?</plist>", raw, re.S)
    return plistlib.loads(m.group(0)) if m else {}


def main(argv):
    profile = None
    if "--profile" in argv:
        i = argv.index("--profile")
        profile = argv[i + 1]
        del argv[i:i + 2]
    out = Path(".")
    if "--out" in argv:
        i = argv.index("--out")
        out = Path(argv[i + 1])
        del argv[i:i + 2]
    names = [a for a in argv if not a.startswith("--")]
    sys.stdout.reconfigure(encoding="utf-8")
    api = Api(profile)
    fields = "fields[profiles]=name,uuid,profileState,profileType,expirationDate,profileContent"
    if "--list" in argv:
        url = ("/v1/profiles?limit=200&fields[profiles]=name,profileState,profileType,expirationDate,bundleId"
               "&include=bundleId&fields[bundleIds]=identifier,seedId")
        while url:
            page = api.get(url)
            bundles = {i["id"]: i["attributes"] for i in page.get("included", [])}
            for p in page["data"]:
                a = p["attributes"]
                b = bundles.get(((p["relationships"].get("bundleId") or {}).get("data") or {}).get("id"), {})
                print(f"{a['profileState']:<8} {a['profileType']:<18} expires {a['expirationDate'][:10]}  "
                      f"team {b.get('seedId', '?'):<10} {b.get('identifier', '?'):<40} {a['name']}")
            url = (page.get("links") or {}).get("next")
        return
    if not names:
        sys.exit(__doc__)
    out.mkdir(parents=True, exist_ok=True)
    missing = False
    for name in names:
        found = [p for p in api.get_all(f"/v1/profiles?filter[name]={name.replace(' ', '%20')}&limit=200&{fields}")
                 if p["attributes"]["name"] == name]
        active = [p for p in found if p["attributes"]["profileState"] == "ACTIVE"]
        if not active:
            print(f"MISSING  {name}: " + ("found but not ACTIVE (expired or invalidated)" if found else "no profile with this exact name"))
            missing = True
            continue
        # Several profiles can share one name; take the one that expires last.
        p = max(active, key=lambda x: x["attributes"]["expirationDate"])["attributes"]
        raw = base64.b64decode(p["profileContent"])
        (out / f"{p['uuid']}.mobileprovision").write_bytes(raw)
        ent = embedded_plist(raw).get("Entitlements", {})
        groups = ent.get("com.apple.security.application-groups", [])
        note = f"  ({len(active)} active profiles share this name)" if len(active) > 1 else ""
        print(f"SAVED    {name} -> {p['uuid']}.mobileprovision  {ent.get('application-identifier', '?')}  "
              f"expires {p['expirationDate'][:10]}  app groups: {', '.join(groups) or 'none'}{note}")
    sys.exit(2 if missing else 0)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except ApiError as e:
        print(e.describe())
        sys.exit(4)

#!/usr/bin/env python3
"""Upload an .ipa to App Store Connect with the Build Upload API. No Mac, altool or Transporter needed,
so an IPA built elsewhere (a Mac that is now asleep, a CI artifact) can be uploaded from Windows or Linux.

  python upload_ipa.py App.ipa APP_ID --dry-run     check only
  python upload_ipa.py App.ipa APP_ID               upload, then wait for the upload to be accepted
  python upload_ipa.py App.ipa APP_ID --wait 20     also wait up to 20 minutes for the build to finish processing
  python upload_ipa.py --profile clientteam App.ipa APP_ID

It refuses to upload when the IPA's bundle id is not the app's, or when that build number already exists.
Exit codes: 0 ok, 2 refused or failed, 4 API error.
"""
import hashlib
import os
import plistlib
import re
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from asc_api import Api, ApiError  # noqa: E402


def ipa_info(path):
    with zipfile.ZipFile(path) as z:
        name = next((n for n in z.namelist() if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist", n)), None)
        if not name:
            sys.exit("not an IPA: no Payload/<App>.app/Info.plist inside")
        info = plistlib.loads(z.read(name))
    return info["CFBundleShortVersionString"], info["CFBundleVersion"], info["CFBundleIdentifier"]


def put_part(op, chunk, label):
    req = urllib.request.Request(op["url"], data=chunk, method=op["method"])
    for h in op.get("requestHeaders") or []:
        req.add_header(h["name"], h["value"])
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                print(f"  {label}: {len(chunk):,} bytes -> {r.status}", flush=True)
                return
        except Exception as e:  # network errors on a large PUT are worth retrying
            print(f"  {label}: attempt {attempt + 1} failed: {e!r}", flush=True)
            time.sleep(5)
    print(f"upload of {label} failed after 4 attempts")
    sys.exit(2)


def main(argv):
    profile = None
    if "--profile" in argv:
        i = argv.index("--profile")
        profile = argv[i + 1]
        del argv[i:i + 2]
    wait = 0
    if "--wait" in argv:
        i = argv.index("--wait")
        wait = int(argv[i + 1])
        del argv[i:i + 2]
    dry = "--dry-run" in argv or "--dry" in argv
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    ipa, app = args
    sys.stdout.reconfigure(encoding="utf-8")
    api = Api(profile)

    short, build, bundle = ipa_info(ipa)
    size = os.path.getsize(ipa)
    data = Path(ipa).read_bytes()
    md5 = hashlib.md5(data).hexdigest()
    print(f"IPA     {os.path.basename(ipa)}  {size:,} bytes  md5 {md5}")
    print(f"        {bundle}  version {short}  build {build}")

    record = api.get(f"/v1/apps/{app}?fields[apps]=bundleId,name")["data"]["attributes"]
    print(f"APP     {record['name']}  {record['bundleId']}")
    if record["bundleId"] != bundle:
        print(f"REFUSED: the IPA is {bundle} but app {app} is {record['bundleId']}")
        sys.exit(2)
    existing = api.get(f"/v1/builds?filter[app]={app}&filter[version]={build}&fields[builds]=version,processingState")["data"]
    if existing:
        print(f"REFUSED: build {build} is already on App Store Connect ({existing[0]['attributes']['processingState']}). "
              "Bump the build number and rebuild.")
        sys.exit(2)
    if dry:
        print("Dry run: checks passed, nothing uploaded.")
        return

    up = api.post("/v1/buildUploads", {"data": {
        "type": "buildUploads",
        "attributes": {"cfBundleShortVersionString": short, "cfBundleVersion": build, "platform": "IOS"},
        "relationships": {"app": {"data": {"type": "apps", "id": app}}}}})["data"]
    f = api.post("/v1/buildUploadFiles", {"data": {
        "type": "buildUploadFiles",
        "attributes": {"assetType": "ASSET", "fileName": os.path.basename(ipa), "fileSize": size, "uti": "com.apple.ipa"},
        "relationships": {"buildUpload": {"data": {"type": "buildUploads", "id": up["id"]}}}}})["data"]
    ops = f["attributes"]["uploadOperations"]
    print(f"UPLOAD  {up['id']}  in {len(ops)} part(s)")
    for i, op in enumerate(ops, 1):
        put_part(op, data[op["offset"]:op["offset"] + op["length"]], f"part {i}/{len(ops)}")
    api.patch(f"/v1/buildUploadFiles/{f['id']}", {"data": {
        "type": "buildUploadFiles", "id": f["id"],
        "attributes": {"uploaded": True, "sourceFileChecksums": {"file": {"hash": md5, "algorithm": "MD5"}}}}})

    state = None
    for _ in range(60):
        raw = api.get(f"/v1/buildUploads/{up['id']}")["data"]["attributes"].get("state") or {}
        state = raw.get("state") if isinstance(raw, dict) else raw
        print(f"STATE   {state}", flush=True)
        if state in ("COMPLETE", "FAILED"):
            if state == "FAILED":
                print(raw)
            break
        time.sleep(15)
    if state != "COMPLETE":
        print("The upload was not accepted. Check the email Apple sends to the uploader for the reason.")
        sys.exit(2)

    deadline = time.time() + wait * 60
    while wait:
        found = api.get(f"/v1/builds?filter[app]={app}&filter[version]={build}&fields[builds]=processingState")["data"]
        processing = found[0]["attributes"]["processingState"] if found else "not visible yet"
        print(f"BUILD   {processing}", flush=True)
        if processing == "VALID":
            break
        if processing in ("INVALID", "FAILED") or time.time() > deadline:
            sys.exit(2)
        time.sleep(30)
    print(f"Uploaded {short} ({build}).")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except ApiError as e:
        print(e.describe())
        sys.exit(4)

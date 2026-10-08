#!/usr/bin/env python3
"""Where an app stands on App Store Connect, and what is in the way of the next release. Read-only.

  python asc_status.py APP_ID                     one report
  python asc_status.py APP_ID --json              the same as JSON
  python asc_status.py APP_ID --watch             poll until App Review decides
  python asc_status.py APP_ID --watch --timeout 6h --interval 10m
  python asc_status.py --profile clientteam APP_ID

Exit codes: 0 report printed, or (with --watch) approved / live
            1 rejected, or App Review is waiting on the developer
            2 a problem that blocks releases (agreement, missing availability)
            3 --watch found nothing in review (never submitted, or the submission was cancelled)
            4 API error
            7 --watch timed out with the review still pending
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from asc_api import Api, ApiError  # noqa: E402

IN_REVIEW = {"WAITING_FOR_REVIEW", "IN_REVIEW", "WAITING_FOR_EXPORT_COMPLIANCE"}
REJECTED = {"REJECTED", "METADATA_REJECTED", "INVALID_BINARY"}
APPROVED = {"ACCEPTED", "PENDING_DEVELOPER_RELEASE", "PENDING_APPLE_RELEASE", "PROCESSING_FOR_APP_STORE", "READY_FOR_SALE"}


def seconds(text):
    unit = {"s": 1, "m": 60, "h": 3600}.get(text[-1])
    return int(text[:-1]) * unit if unit else int(text)


def collect(api, app):
    info = api.get(f"/v1/apps/{app}?fields[apps]=name,bundleId,primaryLocale")["data"]["attributes"]
    report = {"app": app, "name": info["name"], "bundleId": info["bundleId"], "problems": [], "notes": []}

    v = api.get(f"/v1/apps/{app}/appStoreVersions?filter[platform]=IOS&limit=6"
                "&fields[appStoreVersions]=versionString,appStoreState,releaseType,createdDate,build"
                "&include=build&fields[builds]=version,processingState")
    builds = {i["id"]: i["attributes"] for i in v.get("included", []) if i["type"] == "builds"}
    report["versions"] = []
    for d in v["data"]:
        b = ((d.get("relationships") or {}).get("build") or {}).get("data") or {}
        report["versions"].append({"version": d["attributes"]["versionString"], "state": d["attributes"]["appStoreState"],
                                   "releaseType": d["attributes"].get("releaseType"), "created": d["attributes"]["createdDate"][:10],
                                   "build": builds.get(b.get("id"), {}).get("version")})

    subs = api.get_all(f"/v1/apps/{app}/reviewSubmissions?filter[platform]=IOS&limit=50"
                       "&filter[state]=READY_FOR_REVIEW,WAITING_FOR_REVIEW,IN_REVIEW,UNRESOLVED_ISSUES,CANCELING"
                       "&fields[reviewSubmissions]=state,submittedDate")
    report["submissions"] = [{"id": s["id"], "state": s["attributes"]["state"], "submitted": (s["attributes"].get("submittedDate") or "")[:16]}
                             for s in subs if s["attributes"]["state"] != "COMPLETE"]

    b = api.get(f"/v1/builds?filter[app]={app}&limit=5&sort=-uploadedDate"
                "&fields[builds]=version,processingState,uploadedDate,expired,usesNonExemptEncryption,preReleaseVersion"
                "&include=preReleaseVersion&fields[preReleaseVersions]=version")
    pre = {i["id"]: i["attributes"]["version"] for i in b.get("included", [])}
    report["builds"] = []
    for d in b["data"]:
        p = ((d.get("relationships") or {}).get("preReleaseVersion") or {}).get("data") or {}
        a = d["attributes"]
        report["builds"].append({"version": pre.get(p.get("id")), "build": a["version"], "state": a["processingState"],
                                 "uploaded": a["uploadedDate"][:16], "expired": a["expired"], "encryptionAnswered": a["usesNonExemptEncryption"] is not None})

    # Pricing and availability are separate steps. An approved app with no availability record is on sale nowhere.
    try:
        api.get(f"/v1/apps/{app}/appAvailabilityV2")
        states = {}
        for t in api.get_all(f"/v2/appAvailabilities/{app}/territoryAvailabilities?limit=200&fields[territoryAvailabilities]=available,contentStatuses"):
            for s in t["attributes"].get("contentStatuses") or ["UNKNOWN"]:
                states[s] = states.get(s, 0) + 1
        report["availability"] = states
        if states.get("TRADER_STATUS_NOT_PROVIDED"):
            report["notes"].append(f"{states['TRADER_STATUS_NOT_PROVIDED']} EU territories are off sale until the Digital Services Act "
                                   "trader status is declared (App Store Connect > Business > Compliance, web only).")
    except ApiError as e:
        if e.status != 404:
            raise
        report["availability"] = None
        report["problems"].append("No availability record: the app is offered in no country, even after approval. "
                                  "Set it under Pricing and Availability, or POST /v2/appAvailabilities (references/first-release.md).")

    iaps = []
    for g in api.get_all(f"/v1/apps/{app}/subscriptionGroups?limit=50"):
        for s in api.get_all(f"/v1/subscriptionGroups/{g['id']}/subscriptions?limit=50"):
            iaps.append({"kind": "subscription", "productId": s["attributes"]["productId"], "state": s["attributes"]["state"]})
    for i in api.get_all(f"/v1/apps/{app}/inAppPurchasesV2?limit=50"):
        iaps.append({"kind": "inAppPurchase", "productId": i["attributes"]["productId"], "state": i["attributes"]["state"]})
    report["purchases"] = iaps

    newest = report["versions"][0] if report["versions"] else None
    if any(s["state"] == "UNRESOLVED_ISSUES" for s in report["submissions"]) or (newest and newest["state"] in REJECTED):
        report["problems"].append("App Review rejected the submission or is waiting on you. The message is only in the "
                                  "Resolution Center on the web (references/rejections.md).")
    empty = sum(1 for s in report["submissions"] if s["state"] == "READY_FOR_REVIEW")
    if empty:
        report["notes"].append(f"{empty} draft review submission(s) in READY_FOR_REVIEW. They cannot be deleted; asc_submit.py reuses one.")
    waiting = [p["productId"] for p in iaps if p["state"] == "READY_TO_SUBMIT"]
    if waiting:
        report["notes"].append("Purchases not yet in review: " + ", ".join(waiting) + ". Submit them with a version (--with-iaps).")
    if newest and newest["state"] == "PENDING_DEVELOPER_RELEASE":
        report["notes"].append(f"{newest['version']} is approved and waiting for a manual release.")
    return report


def verdict(report):
    """approved | rejected | pending | idle, from the newest version."""
    if not report["versions"]:
        return "idle"
    state = report["versions"][0]["state"]
    if state in REJECTED or any(s["state"] == "UNRESOLVED_ISSUES" for s in report["submissions"]):
        return "rejected"
    if state in IN_REVIEW:
        return "pending"
    if state in APPROVED:
        return "approved"
    return "idle"


def show(report):
    print(f"{report['name']}  ({report['bundleId']}, app {report['app']})")
    print("Versions:")
    for v in report["versions"]:
        print(f"  {v['version']:<10} build {str(v['build'] or '-'):<5} {v['state']:<28} {v['releaseType'] or '':<15} created {v['created']}")
    print("Latest builds:")
    for b in report["builds"]:
        flags = ("  expired" if b["expired"] else "") + ("" if b["encryptionAnswered"] else "  export compliance not answered")
        print(f"  {str(b['version']):<10} ({b['build']})  {b['state']:<12} uploaded {b['uploaded']}{flags}")
    if report["submissions"]:
        print("Open review submissions:")
        for s in report["submissions"]:
            print(f"  {s['id']}  {s['state']:<20} {s['submitted']}")
    if report["availability"] is not None:
        print("Availability:", ", ".join(f"{n} {s}" for s, n in sorted(report["availability"].items(), key=lambda x: -x[1])))
    if report["purchases"]:
        print("Purchases:", ", ".join(f"{p['productId']} {p['state']}" for p in report["purchases"]))
    for n in report["notes"]:
        print("NOTE:", n)
    for p in report["problems"]:
        print("PROBLEM:", p)
    print("Review verdict:", verdict(report))


def main(argv):
    profile = None
    if "--profile" in argv:
        i = argv.index("--profile")
        profile = argv[i + 1]
        del argv[i:i + 2]
    opt = lambda name, default: argv[argv.index(name) + 1] if name in argv else default  # noqa: E731
    apps = [a for a in argv if a.isdigit()]
    if not apps:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")
    api = Api(profile)
    deadline = time.time() + seconds(opt("--timeout", "2h"))
    interval = seconds(opt("--interval", "5m"))
    try:
        while True:
            report = collect(api, apps[0])
            result = verdict(report)
            if "--watch" not in argv or result in ("approved", "rejected", "idle"):
                break
            print(time.strftime("%H:%M"), report["versions"][0]["version"], report["versions"][0]["state"], flush=True)
            if time.time() + interval > deadline:
                print("Still in review at the timeout.")
                sys.exit(7)
            time.sleep(interval)
    except ApiError as e:
        if e.agreement_blocked:
            print("PROBLEM: App Store Connect is refusing API calls until the Account Holder accepts an updated agreement or "
                  "renews the membership (developer.apple.com/account, then App Store Connect > Business).\n" + e.describe())
            sys.exit(2)
        print(e.describe())
        sys.exit(4)
    print(json.dumps(report, indent=1)) if "--json" in argv else show(report)
    if "--watch" in argv:
        sys.exit({"approved": 0, "rejected": 1}.get(result, 3))
    sys.exit(1 if result == "rejected" else 2 if report["problems"] else 0)


if __name__ == "__main__":
    main(sys.argv[1:])

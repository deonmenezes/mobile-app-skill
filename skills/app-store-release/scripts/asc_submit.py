#!/usr/bin/env python3
"""Put an uploaded build on an App Store version and submit it for App Review.

Without --submit this is a dry run: it only reads, and prints the plan and anything that would block it.

  python asc_submit.py --app APP_ID --version 1.2.0 --build 7
  python asc_submit.py --app APP_ID --version 1.2.0 --build 7 --whats-new notes.txt --submit

  --whats-new FILE         What's New text for --locale (default: the app's primary locale)
  --whats-new-all          also use that text for every other locale that has none
  --notes FILE             replace the App Review notes (4000 characters at most)
  --release-type TYPE      AFTER_APPROVAL or MANUAL. Left as it is when not given (new versions: AFTER_APPROVAL)
  --phased                 turn on the 7-day phased release (updates only)
  --replace-in-review      if a version is in review, or a rejected submission is still open, cancel it first
  --encryption-exempt      answer export compliance "no non-exempt encryption" if the build has no answer
  --with-iaps              submit in-app purchases and subscriptions that are READY_TO_SUBMIT with this version
  --wait-processing MIN    wait this long for the build to finish processing (default 20)
  --retry-min MIN          keep retrying while App Store Connect answers 5xx (default 30)
  --profile NAME           credentials profile (see asc_api.py)

Everything that can be checked is checked before the first change, so a blocked run changes nothing.
Exit codes: 0 submitted, already submitted, or dry run with no blockers
            2 blocked: something has to change first (printed)
            3 blocked by an agreement only the Account Holder can accept
            4 API error
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from asc_api import Api, ApiError  # noqa: E402

IN_REVIEW = {"WAITING_FOR_REVIEW", "IN_REVIEW"}
OPEN_SUBMISSION = {"WAITING_FOR_REVIEW", "IN_REVIEW", "UNRESOLVED_ISSUES"}
EDITABLE = {"PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED", "METADATA_REJECTED", "INVALID_BINARY", "READY_FOR_REVIEW"}
RELEASED = {"READY_FOR_SALE", "REPLACED_WITH_NEW_VERSION", "PROCESSING_FOR_APP_STORE", "PENDING_APPLE_RELEASE",
            "REMOVED_FROM_SALE", "DEVELOPER_REMOVED_FROM_SALE"}
REVIEW_DETAIL_FIELDS = ("contactFirstName", "contactLastName", "contactPhone", "contactEmail",
                        "demoAccountName", "demoAccountPassword", "demoAccountRequired", "notes")


class Blocked(Exception):
    pass


def state_of(version):
    return version["attributes"]["appStoreState"]


class Run:
    def __init__(self, args):
        self.a = args
        self.api = Api(args.profile)
        self.live = args.submit
        self.blockers = []
        self.changed = False
        self.attempted = set()

    def step(self, text, fn):
        """Print the step; run it only on a real run."""
        if not self.live:
            print("  would: " + text)
            return None
        print("  " + text, flush=True)
        self.changed = True
        return fn()

    def block(self, text):
        self.blockers.append(text)
        print("  BLOCKER: " + text)

    def read_file(self, path, what):
        p = Path(path)
        if not p.is_file():
            raise Blocked(f"{what} file not found: {path}")
        text = p.read_text(encoding="utf-8").strip()
        if not text:
            raise Blocked(f"{what} file is empty: {path}")
        if len(text) > 4000:
            raise Blocked(f"{what} is {len(text)} characters; the limit is 4000.")
        return text

    # ------------------------------------------------------------------ reads
    def find_build(self):
        a = self.a
        path = (f"/v1/builds?filter[app]={a.app}&filter[version]={a.build}&filter[preReleaseVersion.version]={a.version}"
                "&fields[builds]=version,processingState,expired,usesNonExemptEncryption")
        deadline = time.time() + a.wait_processing * 60
        while True:
            found = self.api.get(path)["data"]
            state = found[0]["attributes"]["processingState"] if found else None
            if state == "VALID":
                return found[0]
            if state in ("INVALID", "FAILED"):
                raise Blocked(f"build {a.version} ({a.build}) failed processing ({state}). Apple emails the reason to the uploader.")
            if not self.live or time.time() > deadline:
                raise Blocked(f"build {a.version} ({a.build}) is " + (f"still {state}" if state else "not on App Store Connect yet")
                              + ". Upload it, or wait for processing, then run again.")
            print(f"  build {a.version} ({a.build}): {state or 'not visible yet'}, waiting", flush=True)
            time.sleep(30)

    def versions(self):
        return self.api.get(f"/v1/apps/{self.a.app}/appStoreVersions?filter[platform]=IOS&limit=10"
                            "&fields[appStoreVersions]=versionString,appStoreState,releaseType,build&include=build&fields[builds]=version")["data"]

    def submissions(self, states):
        """Review submissions in the given states, each with the ids of the app versions it holds and its item count."""
        out = []
        for s in self.api.get_all(f"/v1/apps/{self.a.app}/reviewSubmissions?filter[platform]=IOS&filter[state]={','.join(states)}&limit=50"):
            items = self.api.get_all(f"/v1/reviewSubmissions/{s['id']}/items?limit=50&include=appStoreVersion&fields[appStoreVersions]=versionString")
            held = [((i.get("relationships") or {}).get("appStoreVersion") or {}).get("data") for i in items]
            out.append({"id": s["id"], "state": s["attributes"]["state"], "items": len(items),
                        "versions": [v["id"] for v in held if v]})
        return out

    def purchases(self):
        out = []
        for g in self.api.get_all(f"/v1/apps/{self.a.app}/subscriptionGroups?limit=50"):
            for s in self.api.get_all(f"/v1/subscriptionGroups/{g['id']}/subscriptions?limit=50"):
                out.append(("subscription", s["id"], s["attributes"]["productId"], s["attributes"]["state"]))
        for i in self.api.get_all(f"/v1/apps/{self.a.app}/inAppPurchasesV2?limit=50"):
            out.append(("inAppPurchase", i["id"], i["attributes"]["productId"], i["attributes"]["state"]))
        return out

    def review_detail(self, version_id):
        try:
            return self.api.get(f"/v1/appStoreVersions/{version_id}/appStoreReviewDetail").get("data")
        except ApiError as e:
            if e.status != 404:
                raise
            return None

    def localizations(self, version_id):
        return self.api.get(f"/v1/appStoreVersions/{version_id}/appStoreVersionLocalizations?limit=200"
                            "&fields[appStoreVersionLocalizations]=locale,whatsNew")["data"]

    # ------------------------------------------------------------------- plan
    def plan_whats_new(self, source, target_exists):
        """{locale: text} to set. `source` is the target version, or the newest version when the target is still to be made."""
        a = self.a
        if not self.released:
            print("  first release: What's New does not apply")
            return {}
        locale = a.locale or self.api.get(f"/v1/apps/{a.app}?fields[apps]=primaryLocale")["data"]["attributes"]["primaryLocale"]
        plan = {}
        for loc in self.localizations(source["id"]):
            name = loc["attributes"]["locale"]
            current = loc["attributes"].get("whatsNew") if target_exists else None  # a new version starts with none
            use = self.whats_new_text if self.whats_new_text is not None and (name == locale or (a.whats_new_all and not current)) else None
            if use is not None and use != current:
                plan[name] = use
            elif not current and use is None:
                self.block(f"{name} has no What's New text. Pass --whats-new (with --locale {name}, or --whats-new-all).")
        return plan

    # ---------------------------------------------------------------- changes
    def cancel(self, open_subs, version):
        for s in open_subs:
            self.api.patch(f"/v1/reviewSubmissions/{s['id']}", {"data": {"type": "reviewSubmissions", "id": s["id"],
                                                                          "attributes": {"canceled": True}}})
        for _ in range(48):  # cancelling is asynchronous
            still = self.submissions(sorted(OPEN_SUBMISSION | {"CANCELING"}))
            state = self.api.get(f"/v1/appStoreVersions/{version['id']}?fields[appStoreVersions]=appStoreState")["data"]["attributes"]["appStoreState"]
            if not [s for s in still if s["versions"]] and state not in IN_REVIEW:
                time.sleep(8)  # the version takes a few more seconds to become editable
                return
            time.sleep(5)
        raise Blocked("the old submission is still cancelling. Run the same command again in a few minutes.")

    def create_version(self):
        attrs = {"platform": "IOS", "versionString": self.a.version}
        if self.a.release_type:
            attrs["releaseType"] = self.a.release_type
        return self.api.post("/v1/appStoreVersions", {"data": {"type": "appStoreVersions", "attributes": attrs,
                             "relationships": {"app": {"data": {"type": "apps", "id": self.a.app}}}}})["data"]

    def phased_release(self, version):
        try:
            self.api.post("/v1/appStoreVersionPhasedReleases", {"data": {
                "type": "appStoreVersionPhasedReleases", "attributes": {"phasedReleaseState": "INACTIVE"},
                "relationships": {"appStoreVersion": {"data": {"type": "appStoreVersions", "id": version["id"]}}}}})
        except ApiError as e:
            if e.status != 409:  # 409: this version already has one
                raise

    def set_whats_new(self, version, plan):
        for loc in self.localizations(version["id"]):
            text = plan.get(loc["attributes"]["locale"])
            if text is not None and text != loc["attributes"].get("whatsNew"):
                self.api.patch(f"/v1/appStoreVersionLocalizations/{loc['id']}", {"data": {
                    "type": "appStoreVersionLocalizations", "id": loc["id"], "attributes": {"whatsNew": text}}})

    def ensure_review_detail(self, version, copy_from):
        """A version made through the API starts without App Review details; carry them over from the last version."""
        detail = self.review_detail(version["id"])
        if detail is None and copy_from:
            attrs = {k: v for k, v in copy_from["attributes"].items() if k in REVIEW_DETAIL_FIELDS and v is not None}
            detail = self.api.post("/v1/appStoreReviewDetails", {"data": {"type": "appStoreReviewDetails", "attributes": attrs,
                                   "relationships": {"appStoreVersion": {"data": {"type": "appStoreVersions", "id": version["id"]}}}}})["data"]
        if detail is not None and self.notes_text is not None and detail["attributes"].get("notes") != self.notes_text:
            self.api.patch(f"/v1/appStoreReviewDetails/{detail['id']}", {"data": {"type": "appStoreReviewDetails", "id": detail["id"],
                                                                                 "attributes": {"notes": self.notes_text}}})

    def screenshots_ready(self, version):
        """A submission fails while any screenshot is still processing."""
        for _ in range(40):
            states = []
            for loc in self.localizations(version["id"]):
                for s in self.api.get(f"/v1/appStoreVersionLocalizations/{loc['id']}/appScreenshotSets?limit=50")["data"]:
                    states += [(x["attributes"].get("assetDeliveryState") or {}).get("state")
                               for x in self.api.get(f"/v1/appScreenshotSets/{s['id']}/appScreenshots?limit=50")["data"]]
            if not states:
                return self.block("the version has no screenshots.")
            if any(s == "FAILED" for s in states):
                return self.block("a screenshot failed processing. Replace it in App Store Connect.")
            done = all(s == "COMPLETE" for s in states)
            if done or not self.live:
                print(f"  screenshots: {len(states)}, {'all processed' if done else 'some still processing'}")
                return None
            time.sleep(6)
        return self.block("screenshots are still processing after 4 minutes.")

    def queue_purchases(self):
        for kind, iid, pid, state in self.purchases():
            if state != "READY_TO_SUBMIT":
                continue
            retried = iid in self.attempted
            self.attempted.add(iid)
            try:
                if kind == "subscription":
                    self.api.post("/v1/subscriptionSubmissions", {"data": {"type": "subscriptionSubmissions", "relationships": {
                        "subscription": {"data": {"type": "subscriptions", "id": iid}}}}})
                else:
                    self.api.post("/v1/inAppPurchaseSubmissions", {"data": {"type": "inAppPurchaseSubmissions", "relationships": {
                        "inAppPurchaseV2": {"data": {"type": "inAppPurchases", "id": iid}}}}})
                print(f"    added {pid}")
            except ApiError as e:
                if e.status >= 500:
                    raise
                if retried:  # the earlier attempt landed although it answered with an error
                    print(f"    {pid} was already added on an earlier attempt")
                    continue
                # Seen with an app's first subscriptions: the API refuses and the web UI is the only way in.
                raise Blocked(f"could not add {pid} to the review over the API:\n{e.describe()}\n"
                              "The version was NOT submitted. In App Store Connect open the subscription group (or the purchase) "
                              "and choose \"Add for Review\" so it joins the same draft submission as the version, then run this "
                              "again without --with-iaps.") from None

    def pick_draft(self, version_id):
        """(id or None, already holds this version). Drafts cannot be deleted, so one is reused when it fits."""
        drafts = self.submissions(["READY_FOR_REVIEW"])
        for d in drafts:
            if version_id in d["versions"]:
                return d, True
        for d in drafts:
            if d["items"] == 0:
                return d, False
        return None, False

    def submit(self, version):
        deadline = time.time() + self.a.retry_min * 60
        self.changed = True
        tried = False
        while True:
            try:
                if tried:  # an attempt that answered 5xx may still have gone through
                    state = self.api.get(f"/v1/appStoreVersions/{version['id']}?fields[appStoreVersions]=appStoreState")["data"]["attributes"]["appStoreState"]
                    if state in IN_REVIEW:
                        return "(submitted on an earlier attempt)"
                tried = True
                draft, has_version = self.pick_draft(version["id"])
                sid = draft["id"] if draft else self.api.post("/v1/reviewSubmissions", {"data": {
                    "type": "reviewSubmissions", "attributes": {"platform": "IOS"},
                    "relationships": {"app": {"data": {"type": "apps", "id": self.a.app}}}}})["data"]["id"]
                if not has_version:
                    self.api.post("/v1/reviewSubmissionItems", {"data": {"type": "reviewSubmissionItems", "relationships": {
                        "reviewSubmission": {"data": {"type": "reviewSubmissions", "id": sid}},
                        "appStoreVersion": {"data": {"type": "appStoreVersions", "id": version["id"]}}}}})
                if self.a.with_iaps:
                    self.queue_purchases()  # re-read every attempt, so a retry never adds one twice
                held = next((s for s in self.submissions(["READY_FOR_REVIEW"]) if s["id"] == sid), None)
                if not held or version["id"] not in held["versions"]:
                    raise Blocked(f"submission {sid} does not hold version {self.a.version}. Nothing was submitted; look at it in App Store Connect.")
                print(f"    submission {sid} holds {held['items']} item(s), including version {self.a.version}")
                self.api.patch(f"/v1/reviewSubmissions/{sid}", {"data": {"type": "reviewSubmissions", "id": sid,
                                                                         "attributes": {"submitted": True}}})
                return sid
            except ApiError as e:
                if e.agreement_blocked:
                    print(e.describe())
                    print("The Account Holder has to accept the latest agreement (developer.apple.com/account, then "
                          "App Store Connect > Business). The API cannot do it. Run the same command again afterwards.")
                    sys.exit(3)
                # Apple answers 5xx on new items for a while after a developer cancel.
                if e.status >= 500 and time.time() < deadline:
                    print(f"    App Store Connect answered {e.status}; retrying in 3 minutes", flush=True)
                    time.sleep(180)
                    continue
                raise

    # -------------------------------------------------------------------- run
    def run(self):
        a = self.a
        self.whats_new_text = self.read_file(a.whats_new, "What's New") if a.whats_new else None
        self.notes_text = self.read_file(a.notes, "review notes") if a.notes else None
        app = self.api.get(f"/v1/apps/{a.app}?fields[apps]=name,bundleId")["data"]["attributes"]
        print(f"{app['name']} ({app['bundleId']}): version {a.version}, build {a.build}" + ("" if self.live else "   [dry run]"))

        # ---- read everything and decide, before changing anything
        build = self.find_build()
        print(f"  build is VALID ({build['id']})")
        if build["attributes"]["expired"]:
            raise Blocked("that build has expired. Upload a new one.")
        answer_compliance = build["attributes"]["usesNonExemptEncryption"] is None
        if answer_compliance and not a.encryption_exempt:
            self.block("export compliance is unanswered for this build. Pass --encryption-exempt if the app only uses "
                       "exempt encryption (HTTPS), or set ITSAppUsesNonExemptEncryption in Info.plist for future builds.")

        versions = self.versions()
        self.released = any(state_of(v) in RELEASED for v in versions)
        if any(v["attributes"]["versionString"] == a.version and state_of(v) in RELEASED for v in versions):
            raise Blocked(f"{a.version} has already been released. Bump the version number and build again.")
        pending = next((v for v in versions if state_of(v) == "PENDING_DEVELOPER_RELEASE"), None)
        if pending:
            raise Blocked(f"{pending['attributes']['versionString']} is approved and waiting for a manual release. "
                          "Release it or reject it in App Store Connect before submitting another version.")

        in_review = next((v for v in versions if state_of(v) in IN_REVIEW), None)
        if in_review:
            attached = ((in_review["relationships"].get("build") or {}).get("data") or {}).get("id")
            if in_review["attributes"]["versionString"] == a.version and attached == build["id"]:
                print(f"  {a.version} ({a.build}) is already {state_of(in_review)}. Nothing to do.")
                return 0
        version = in_review or next((v for v in versions if state_of(v) in EDITABLE), None)

        # Only submissions that hold an app version are in the way (an in-app event on its own is not).
        open_subs = [s for s in self.submissions(sorted(OPEN_SUBMISSION)) if s["versions"]]
        if open_subs and not a.replace_in_review:
            if in_review:
                raise Blocked(f"{in_review['attributes']['versionString']} is {state_of(in_review)}. Pass --replace-in-review to cancel "
                              "that submission and send this build instead. Cancelling gives up its place in the queue.")
            raise Blocked("a rejected submission is still open (UNRESOLVED_ISSUES). Reply in the Resolution Center first if there is "
                          "anything to say, because cancelling removes the reply box. Then pass --replace-in-review, or resubmit "
                          "from the Resolution Center thread instead.")
        if in_review and not open_subs:
            raise Blocked(f"{in_review['attributes']['versionString']} is still {state_of(in_review)} but no open submission holds it: "
                          "a cancel is probably still going through. Run this again in a few minutes.")
        if open_subs and version is None:
            raise Blocked("a submission is open but its version is in a state this script does not handle ("
                          + ", ".join(state_of(v) for v in versions) + "). Sort it out in App Store Connect.")
        purchases = self.purchases()
        if open_subs and not a.with_iaps:
            riding = [p[2] for p in purchases if p[3] in IN_REVIEW]
            if riding:
                self.block("the submission being replaced also carries " + ", ".join(riding) + ". Cancelling releases them, and the "
                           "new submission would go without them. Pass --with-iaps to send them again.")

        plan = self.plan_whats_new(version or versions[0], target_exists=version is not None) if versions else {}
        previous_detail = None
        if version is None or self.review_detail(version["id"]) is None:
            for v in versions:
                previous_detail = previous_detail or (self.review_detail(v["id"]) if v is not version else None)
            if previous_detail is None:
                self.block("no version of this app has App Review details (contact name, phone, email). Fill them in once "
                           "in App Store Connect.")
        if version is not None and not open_subs:
            self.screenshots_ready(version)

        if self.blockers:
            print(f"\n{len(self.blockers)} blocker(s). Nothing was changed.")
            return 2

        # ---- from here on a real run changes things
        if open_subs:
            before = {p[2] for p in purchases if p[3] == "READY_TO_SUBMIT"}
            self.step(f"cancel the open submission of {version['attributes']['versionString']} ({', '.join(s['state'] for s in open_subs)})",
                      lambda: self.cancel(open_subs, version))
            if self.live:
                for _ in range(12):  # purchases are released a little after the submission
                    now = self.purchases()
                    if not any(p[3] in IN_REVIEW for p in now):
                        break
                    time.sleep(5)
                released = sorted({p[2] for p in now if p[3] == "READY_TO_SUBMIT"} - before)
                if released and not a.with_iaps:
                    raise Blocked("cancelling released " + ", ".join(released) + " from review. Run the same command again with "
                                  "--with-iaps so they go back in with the version.")
        if answer_compliance:
            self.step("answer export compliance: no non-exempt encryption", lambda: self.api.patch(f"/v1/builds/{build['id']}", {
                "data": {"type": "builds", "id": build["id"], "attributes": {"usesNonExemptEncryption": False}}}))
        if version is None:
            version = self.step(f"create version {a.version}", self.create_version)
        else:
            attrs = {}
            if version["attributes"]["versionString"] != a.version:
                # Before the first release an app has one editable version, so it is renamed, not replaced.
                attrs["versionString"] = a.version
            if a.release_type and version["attributes"].get("releaseType") != a.release_type:
                attrs["releaseType"] = a.release_type
            if attrs:
                self.step(f"update version {version['attributes']['versionString']}: {attrs}", lambda: self.api.patch(
                    f"/v1/appStoreVersions/{version['id']}", {"data": {"type": "appStoreVersions", "id": version["id"], "attributes": attrs}}))
            current = ((version.get("relationships") or {}).get("build") or {}).get("data") or {}
            if current.get("id") == build["id"]:
                build = None  # already attached
        if build is not None:
            self.step(f"attach build {a.build}", lambda: self.api.patch(
                f"/v1/appStoreVersions/{version['id']}/relationships/build", {"data": {"type": "builds", "id": build["id"]}}))
        if a.phased and self.released:
            self.step("turn on phased release", lambda: self.phased_release(version))
        for name, text in plan.items():
            print(f"  {'set' if self.live else 'would: set'} What's New for {name} ({len(text)} characters)")
        if plan and self.live:
            self.changed = True
            self.set_whats_new(version, plan)
        if previous_detail is not None or self.notes_text is not None:
            what = ("copy the App Review details from the last version" if previous_detail is not None else "") \
                + (" and " if previous_detail is not None and self.notes_text is not None else "") \
                + (f"replace the review notes ({len(self.notes_text)} characters)" if self.notes_text is not None else "")
            self.step(what, lambda: self.ensure_review_detail(version, previous_detail))
        if self.live:
            self.screenshots_ready(version)

        # On a dry run the purchases in the submission being replaced have not been released yet; count them as ready.
        waiting = {"READY_TO_SUBMIT"} | (IN_REVIEW if open_subs and not self.live else set())
        ready = [p[2] for p in (self.purchases() if self.live else purchases) if p[3] in waiting]
        if ready and a.with_iaps:
            print(f"  {'adding' if self.live else 'would: add'} to this review: " + ", ".join(ready))
        elif ready:
            print("  NOTE: not in this review (pass --with-iaps to include them): " + ", ".join(ready))
        draft, has_version = self.pick_draft(version["id"] if version else None)
        if draft:
            print(f"  {'using' if self.live else 'would: use'} draft submission {draft['id']} ({draft['items']} item(s) in it now)")

        if self.blockers:
            print(f"\n{len(self.blockers)} blocker(s). The version was prepared but NOT submitted.")
            return 2
        if not self.live:
            print("  would: submit for App Review\n\nDry run only. Add --submit to do it.")
            return 0
        print("  submit for App Review", flush=True)
        sid = self.submit(version)
        state = self.api.get(f"/v1/appStoreVersions/{version['id']}?fields[appStoreVersions]=appStoreState")["data"]["attributes"]["appStoreState"]
        print(f"\nSubmitted. Review submission {sid}; version {a.version} is {state}.")
        return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--app", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--build", required=True)
    p.add_argument("--whats-new")
    p.add_argument("--whats-new-all", action="store_true")
    p.add_argument("--locale")
    p.add_argument("--notes")
    p.add_argument("--release-type", choices=["AFTER_APPROVAL", "MANUAL"])
    p.add_argument("--phased", action="store_true")
    p.add_argument("--replace-in-review", action="store_true")
    p.add_argument("--encryption-exempt", action="store_true")
    p.add_argument("--with-iaps", action="store_true")
    p.add_argument("--wait-processing", type=int, default=20)
    p.add_argument("--retry-min", type=int, default=30)
    p.add_argument("--profile")
    p.add_argument("--submit", action="store_true")
    args = p.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    run = Run(args)
    try:
        sys.exit(run.run())
    except Blocked as e:
        print(f"  BLOCKER: {e}\n\n" + ("Stopped part way: the steps printed above were made, but nothing was submitted."
                                       if run.changed else "Nothing was changed."))
        sys.exit(2)
    except ApiError as e:
        print(e.describe())
        if run.changed:
            print("Stopped part way: the steps printed above were made, but nothing was submitted.")
        sys.exit(3 if e.agreement_blocked else 4)


if __name__ == "__main__":
    main()

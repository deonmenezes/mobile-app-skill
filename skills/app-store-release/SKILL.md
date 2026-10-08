---
name: app-store-release
description: Ship an iOS app update or a first release to the App Store end to end, the way it is actually done across many real releases. Bumps the version, builds and signs on a Mac over SSH (or on a GitHub-hosted Mac when yours is asleep), uploads, waits for processing, submits for App Review, watches the review, handles rejections and hotfixes, and checks the app is really on sale afterwards. Includes its own scripts for Windows, Linux and macOS (what has and has not been exercised is listed in the skill), and a one-time setup interview so later releases need no questions. Use when the user says "ship it", "release an update", "push a new version", "submit to the App Store", "upload to TestFlight", "resubmit", "replace the build in review", "my app got rejected", "hotfix", "why is my approved app not on the store", or "set up release automation".
license: MIT
---

# App Store release

A release loop for iOS apps that already exist as code. It was written from shipping more than thirty App Store versions of native SwiftUI, XcodeGen and Expo apps, mostly from a Windows PC driving a Mac over SSH, and it keeps the fixes for what went wrong along the way.

For building an app from nothing, or for Google Play, use the `mobile-app` skill in this pack. This skill is the iOS half of its "ship" and "watch review" stages, done in depth.

Everything runs through the scripts in [scripts/](scripts/). They need Python 3.9+ with `pip install pyjwt cryptography`, and an App Store Connect API key. They do not need the `asc` CLI, fastlane or a Mac, except for the build itself.

| Script | Does | Changes anything? |
|---|---|---|
| `release_config.py` | Per-app config, version and build bumps | Only local files |
| `asc_status.py` | Where the app stands, what blocks a release, `--watch` for the review | No |
| `mac_release.sh` | On the Mac or CI runner: check, archive, sign, export, upload | Uploads a build in `upload` mode |
| `manual_sign.py` | Switches Release configs to manual signing per bundle id | Project file, restored afterwards |
| `fetch_profiles.py` | Downloads provisioning profiles by name | No |
| `upload_ipa.py` | Uploads an `.ipa` with the Build Upload API, no Mac needed | Uploads a build |
| `asc_submit.py` | Version, build, What's New, notes, purchases, submit. Dry run unless `--submit` | Yes, with `--submit` |
| `asc_availability.py` | Where the app is on sale; creates a missing availability record with `--apply` | Only with `--apply` |
| `asc_api.py` | The API client the others use; also a raw `GET/POST/PATCH` command | As asked |

How far each script has been exercised is stated in [Status of the scripts](#status-of-the-scripts). Read it before trusting a write path.

## Rules

1. **The config decides how much to ask.** `.asc/release.json` has `autonomy`:
   - `submit`: go from bump to "submitted for review" without stopping. Stop only for a blocker, a rejection, or anything that would cancel a submission already in review.
   - `testflight`: stop after the build is uploaded and processed. Submit when the user says so.
   - `ask`: show the dry run and wait for a yes before each upload and each submission.
   With no config yet, behave as `ask` and run the setup first.
2. **Always dry-run `asc_submit.py` first**, even under `submit`. It is free, and its blockers are the whole pre-flight check.
3. **Never cancel a submission that is in review without the user's say-so**, whatever the autonomy level. Cancelling throws away the place in the queue and closes the Resolution Center thread.
4. **One build number, one upload.** A build number can never be reused, even after a failed upload. Bump it for every archive.
5. **Report the furthest state you verified, not the one you expect.** "Uploaded" means App Store Connect lists the build as `VALID`. "Submitted" means the version is `WAITING_FOR_REVIEW`. Never promise approval or a review time.
6. **Secrets stay out of the repository and out of the chat.** The config holds ids, names and paths only.
7. **When something fails, check [references/gotchas.md](references/gotchas.md) before improvising.** Most failures here have happened before and have a known cause.

## Setup (once per app)

Do this the first time, or when `.asc/release.json` is missing. Full detail and the exact questions are in [references/setup.md](references/setup.md).

1. From the app's repository root: `python <skill>/scripts/release_config.py init`. It detects the project kind (Expo, XcodeGen, plain Xcode), the bundle id, the scheme and where the version numbers live.
2. Make sure an API key profile exists (`~/.config/appstoreconnect/credentials.env`) and works: `python scripts/asc_api.py apps`. The app must be in that list. If it is not, the key belongs to another Apple team.
3. Fill what can be looked up: `app_id` from the `apps` list; `team_id` and `signing.profiles` from `python scripts/fetch_profiles.py --list`, which prints the team id, bundle id and name of every profile.
4. **Ask the user the setup questions** in [references/setup.md](references/setup.md#questions-to-ask): autonomy, build hosts, how rejections are read, release type, and export compliance. Ask them once, write the answers into the config, and do not ask again on later releases.
5. `python scripts/release_config.py show` must end with "Config is complete."
6. Commit `.asc/release.json`.

A brand-new app that has never been on the store needs more than this. Follow [references/first-release.md](references/first-release.md) before the first submission.

## The release loop

### 1. Look before touching anything

```bash
python scripts/asc_status.py APP_ID
```

Read the whole report. It changes what happens next:

| The report says | Then |
|---|---|
| Newest version `READY_FOR_SALE` | Normal update. Continue. |
| A version is `WAITING_FOR_REVIEW` or `IN_REVIEW` | Something is already in flight. Either wait for it, or this is a hotfix: see [Replacing a build in review](#replacing-a-build-in-review). |
| `REJECTED`, `METADATA_REJECTED` or a submission in `UNRESOLVED_ISSUES` | Read the rejection first: [references/rejections.md](references/rejections.md). Do not resubmit unchanged. |
| `PENDING_DEVELOPER_RELEASE` | An approved version is waiting for a manual release. Ask the user: release it, or replace it. |
| "refusing API calls until the Account Holder accepts" | Stop. Only the account holder can fix it, on the web. Nothing else will work until then. |
| "No availability record" | Fix with `asc_availability.py` before anything else. |

### 2. Version and build

```bash
python scripts/release_config.py show                       # current numbers
python scripts/release_config.py bump --patch --build auto  # 1.2.3 -> 1.2.4, build = highest anywhere + 1
```

- A released version number cannot be submitted again. Any update needs a new one.
- The default for "ship an update" with no number given is a patch bump. Use `--minor` for new features if the user says so.
- `--build auto` reads the highest build number already on App Store Connect, so a build number is never reused.
- A hotfix for a version still in review keeps the version and takes only a new build: `bump --build auto`.
- After a project generator runs (`xcodegen generate`, `expo prebuild`), the archive can silently carry 1.0 (1). `mac_release.sh` refuses an archive whose numbers differ from the config's, so do not skip `APP_VERSION` / `APP_BUILD`.

### 3. What's New and review notes

- Write What's New to the file named in `release.whats_new`. Plain sentences about what changed for the user. 4000 characters at most. Every locale the listing has needs text for an update; `--whats-new-all` copies it to locales that have none.
- Review notes (`release.review_notes`) are capped at 4000 characters. Update them whenever a release changes what the reviewer will see: a new paywall, a changed free limit, a new login, a new permission. Stale notes that contradict the app get rejections.
- If App Review asked a question on the last round, answer it in the notes.

Commit the bump and the text together.

### 4. Build and upload

Pick the host in the order `build.hosts` lists. Details, the SSH recipe and the CI setup are in [references/build-hosts.md](references/build-hosts.md).

**On a Mac over SSH** (`mac`):

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 USER@MAC true          # reachable? if not, go to the next host
git push MAC_REMOTE HEAD:refs/heads/BRANCH                       # code to the Mac
ssh USER@MAC 'mkdir -p ~/.cache/app-store-release'
scp <skill>/scripts/* USER@MAC:~/.cache/app-store-release/      # the scripts, every release (overwrites the old copy)
ssh USER@MAC "$(python scripts/release_config.py env | tr '\n' ' ') \
  ASC_KEY_ID=... ASC_ISSUER_ID=... ASC_PRIVATE_KEY_PATH=... bash ~/.cache/app-store-release/mac_release.sh check"
```

Run `check` first. It reports the checkout, disk, power, certificate and profiles, and fails early instead of forty minutes in. Then run the same command with `upload`. Run it under `nohup` with output to a log file and poll the log: an SSH session that drops kills a foreground build. The last line is `MAC_RELEASE_OK upload 1.2.4 (57)` or `MAC_RELEASE_FAILED <step>`.

**On GitHub Actions** (`github`), when the Mac does not answer:

```bash
gh workflow run ios-release.yml --repo OWNER/REPO --ref BRANCH -f mode=upload
gh run watch --repo OWNER/REPO
```

**IPA built elsewhere**: `mac_release.sh ipa` leaves an `.ipa`; copy it off the Mac in one go and upload it from any machine with `python scripts/upload_ipa.py App.ipa APP_ID --wait 20`.

If no host is available, say so and stop. Do not sit in a retry loop against a sleeping Mac.

### 5. Submit

```bash
python scripts/asc_submit.py --app APP_ID --version 1.2.4 --build 57 --whats-new PATH            # dry run
python scripts/asc_submit.py --app APP_ID --version 1.2.4 --build 57 --whats-new PATH --submit   # for real
```

The dry run waits for nothing and changes nothing. Read every `BLOCKER` and `NOTE` line and fix them. With `--submit` it waits for the build to finish processing (usually 3 to 10 minutes after upload), creates or reuses the version, attaches the build, sets the text, waits for screenshots to finish processing, and submits.

The script does not read the config. Pass these flags yourself, from the `release` block of `.asc/release.json`:

| Config | Flag | Meaning |
|---|---|---|
| `release_type` | `--release-type AFTER_APPROVAL` or `MANUAL` | `AFTER_APPROVAL` goes live as soon as Apple approves. Without the flag an existing version keeps its setting |
| `phased` | `--phased` | 7-day phased rollout. Off by default: small apps want fixes out at once |
| `encryption_exempt` | `--encryption-exempt` | Answers export compliance when the build has no answer. Better: set `ITSAppUsesNonExemptEncryption` in Info.plist once |
| `with_iaps` | `--with-iaps` | Sends `READY_TO_SUBMIT` purchases with the version. See [In-app purchases](#in-app-purchases) |
| `review_notes` | `--notes FILE` | Replaces the App Review notes |

Exit code 3 means an agreement only the Account Holder can accept. Tell the user exactly that, then run the same command again once they have.

### 6. Watch the review

```bash
python scripts/asc_status.py APP_ID --watch --timeout 12h --interval 10m
```

Run it in the background. It exits 0 when approved, 1 when rejected, 3 when nothing is in review any more (the submission was cancelled), 7 when still pending at the timeout. Do not cancel a submission because review is slow. For a genuine emergency, the pack's `expedite-review` skill drafts Apple's expedite request.

### 7. After approval

1. `python scripts/asc_status.py APP_ID`: the version should be `READY_FOR_SALE` (or `PENDING_DEVELOPER_RELEASE` for a manual release, which the user then triggers).
2. `python scripts/asc_availability.py APP_ID`: confirm it is actually on sale. `READY_FOR_SALE` with no availability record means on sale nowhere.
3. Open the store page (`https://apps.apple.com/app/idAPP_ID`) and check the version number shown. The page is the truth; the iTunes lookup API can lag a day behind.
4. Tag the commit: `git tag v1.2.4-57 && git push --tags`. The exact source of every shipped build should be recoverable.
5. Tell the user: version, build, when it was submitted and approved, and anything left open.

### 8. If it is rejected

Follow [references/rejections.md](references/rejections.md). In short: the API does not return the reviewer's message, so read it in the Resolution Center (in the browser, signed in) or have the user paste it; decide whether the answer is a reply, new metadata, or a new build; put the answer to any question into the review notes; then resubmit. Reply in the thread before cancelling anything, because cancelling removes the reply box.

## Special cases

### Replacing a build in review

Use when a bug is found while a version waits for review. Confirm with the user first (rule 3).

1. `release_config.py bump --build auto` (same version, new build), build and upload as usual.
2. `asc_submit.py ... --replace-in-review` (dry run, then `--submit`). It cancels the open submission, waits for the version to become editable, attaches the new build, and resubmits. If the old submission carried in-app purchases, add `--with-iaps`: cancelling releases them, and the script refuses to cancel without it.
3. Apple sometimes answers 500 for several minutes after a cancel. The script retries every 3 minutes for `--retry-min` minutes. Let it.

### In-app purchases

- A purchase or subscription going to review for the first time has to ride in the same submission as an app version. `--with-iaps` adds every `READY_TO_SUBMIT` purchase.
- For an app's **first** subscriptions the API can refuse this. The script then stops before submitting and says so. The way in is the web: open the subscription group in App Store Connect, choose "Add for Review" so it joins the version's draft submission, then run `asc_submit.py` again without `--with-iaps`.
- Never let a version that depends on new purchases go to review without them. The reviewer cannot buy what is not in the submission, and the app is rejected.
- After a cancelled submission, purchases fall back to `READY_TO_SUBMIT` and have to be added again.
- Do not change a purchase's price while it is in review.

### More than one Apple team

An API key only sees its own team's apps. Keep one profile per team (`~/.config/appstoreconnect/<name>.env`), set `credentials_profile` in the app's config, and pass `--profile <name>` to the scripts. If `asc_api.py apps` does not list the app, it is the wrong team, not a missing app.

### Expo and React Native

Set `project.prebuild` to the command that generates `ios/` (for example `npm ci && npx expo prebuild --platform ios`). Version and build live in `app.json`; `bump` keeps `android.versionCode` in step when it was already equal to the iOS build number. If prebuild adds an entitlement the App Store profile does not carry (push is the usual one), the archive fails at signing: remove the entitlement with a config plugin or regenerate the profile with the capability.

## Status of the scripts

Stated plainly, so nobody trusts more than was shown.

- **Run against live App Store Connect accounts while writing this skill:** `asc_api.py`, `asc_status.py` (apps that were live, in review, rejected, and never released), `asc_submit.py` in dry-run mode only (already in review, replace in review, already released, expired build, rejected with an open submission, update with and without an existing version, never submitted), `upload_ipa.py` up to its two refusal checks, `fetch_profiles.py`, `asc_availability.py` in report mode.
- **Run against copies of real projects:** `release_config.py` (Expo `app.json`, XcodeGen `project.yml`, a plain `.xcodeproj`), `manual_sign.py`.
- **Not run in this form:** every write in `asc_submit.py --submit`, the upload itself in `upload_ipa.py`, `asc_availability.py --apply`, and `mac_release.sh` as a whole (no Mac was reachable: it passed a syntax check, and its lock, keychain-list, escaping and signal-handling logic were tested on their own under bash on another system). Each is a generalised port of a script that did ship real releases with the same API calls and the same `xcodebuild` and `security` commands, and the code was reviewed by a second pass, but a port can break what the original got right. Watch the first real use of each.
- **Never run:** `templates/ios-release.yml`.

When one of these does its first real run, fix whatever it turns up and update this section.

## References

- [references/setup.md](references/setup.md): the config file, credentials, and the questions to ask once.
- [references/build-hosts.md](references/build-hosts.md): building on a Mac over SSH, the GitHub Actions fallback, and getting code and scripts to the host.
- [references/first-release.md](references/first-release.md): everything a brand-new app needs before its first submission.
- [references/rejections.md](references/rejections.md): reading a rejection, replying, and resubmitting without losing the thread.
- [references/gotchas.md](references/gotchas.md): every failure met so far, with its cause and fix.

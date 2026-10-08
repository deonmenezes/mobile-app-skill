# Gotchas

Each of these cost time on a real release. Symptom first, then the cause and the fix. Search this page for the error text before trying anything new.

## Account and agreements

| Symptom | Cause and fix |
|---|---|
| Submission fails with 409 and the top-level error says little | The real reason is nested under `meta.associatedErrors`. `asc_api.py` prints it. `STATE_ERROR.DPLA_OUTDATED_ERROR` means Apple published a new licence agreement and the Account Holder has not accepted it. Only they can, on the web. It blocks every app on the team. |
| Every API call returns 403 "A required agreement is missing or has expired" | Either an unaccepted agreement or an **expired Developer Program membership**. The developer account page shows a banner for the second. After renewing, the Paid Applications agreement may need accepting again. |
| No Renew button anywhere | The Apple ID's country was changed after enrolling. Renewal has to go through Apple Developer Support. |
| Approved app missing in the EU only | Digital Services Act trader status not declared: 27 territories show `TRADER_STATUS_NOT_PROVIDED`. Account-wide, web-only (Business > Compliance). |
| `asc_api.py apps` does not list the app | Wrong team. A key only sees the apps of the team that issued it. Use that team's key with `--profile`. |

## Versions and builds

| Symptom | Cause and fix |
|---|---|
| Upload refused, "build already exists" or a silent processing failure | A build number can never be reused, even from a failed upload. `release_config.py bump --build auto`. |
| The archive is 1.0 (1) whatever the config says | A project generator reset it. With XcodeGen, Info.plist must reference `$(MARKETING_VERSION)` and `$(CURRENT_PROJECT_VERSION)`. `mac_release.sh` refuses the archive when `APP_VERSION` / `APP_BUILD` are passed. |
| The submit step attached an old build | A tool defaulting the build number (to 1, or to "latest"). Always pass version and build explicitly. `asc_submit.py` requires both. |
| "A version already exists" when creating a version on a new app | Before the first release an app has exactly one editable version. Rename it instead; `asc_submit.py` does. |
| Versions hardcoded in several files drift apart | Keep one source of truth and let `release_config.py bump` edit it. For unusual layouts list every file in `project.version_files`. `show` warns when they disagree. |
| A build shows as expired | TestFlight builds expire after 90 days. Upload a new one. |

## Signing

| Symptom | Cause and fix |
|---|---|
| `errSecInternalComponent`, or "User interaction is not allowed" from codesign | The login keychain is locked in an SSH session. Sign from a throwaway keychain built from the `.p12` (`mac_release.sh` does), with `set-key-partition-list -S apple-tool:,apple:,codesign:`. |
| Archive wants a development profile or a registered device | Automatic signing. Force manual signing on the Release configuration per target (`manual_sign.py`). |
| "No profiles for 'bundle.id' were found" right after it worked | A project generator ran again and wiped the signing settings. Generate first, sign second, and never run the generator during an archive. |
| The app is signed but an App Group or capability is missing at runtime | The profile was created before the capability was added. Profiles snapshot entitlements. Regenerate it and fetch again; check the App Groups line `fetch_profiles.py` prints. |
| Xcode says the profile is not installed, but the file is there | Xcode 16 and later read `~/Library/Developer/Xcode/UserData/Provisioning Profiles/`; older versions read `~/Library/MobileDevice/Provisioning Profiles/`. Install into both, named `<uuid>.mobileprovision`. |
| Signing fails with "ambiguous" identity | Two certificates share a common name. Sign with the keychain that holds exactly one (the throwaway keychain), or pin the SHA-1. |
| Dozens of profiles with the same name | Tools that mint a new profile on every run. `fetch_profiles.py` picks the active one that expires last; clean the rest up in the portal when convenient. |
| Cannot create another distribution certificate | Teams have a small limit. Reuse the existing `.p12` on every host. |
| Archive fails on an entitlement such as `aps-environment` | A library added an entitlement the profile does not carry. Strip it (an Expo config plugin can) or add the capability and regenerate the profile. |

## Building on a Mac over SSH

| Symptom | Cause and fix |
|---|---|
| `exportArchive` fails with "Copy failed"; the log mentions rsync | Homebrew's rsync is ahead of Apple's on `PATH`. Run the export with `PATH=/usr/bin:/bin:/usr/sbin:/sbin`. |
| `xcodegen`, `fastlane`, `node` not found over SSH | Non-interactive shells do not load the Homebrew path. Export `/opt/homebrew/bin` first. |
| A tool dies with "invalid byte sequence in US-ASCII" | No locale over SSH and non-ASCII text in the release notes. `export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8`. |
| The archive stops with no error, or the Swift compiler is "killed" | Out of memory on a 16 GB Mac, often because two builds overlapped. One build at a time (the lock), and `JOBS=2`. |
| The build dies when the terminal closes | Foreground SSH. Run under `nohup` and poll a log file. |
| A script's `grep -q` fails at random | `set -o pipefail` plus `grep -q` closing the pipe early. Capture the output into a variable, then grep the variable. |
| A temporary file from the last release is gone | `/tmp` is cleared on reboot. Recreate what you need every run; keep nothing important there. |
| The Mac stopped answering mid-release | It slept, or the battery ran out. `mac_release.sh check` refuses to start under 20% on battery. Plug it in. |
| A system alert keeps appearing in the simulator after tests | Stale simulator state, not the app. `xcrun simctl shutdown <id> && xcrun simctl boot <id>`. |
| `git push` to the Mac is refused | Its working tree is dirty and `updateInstead` protects it. `git stash -u` there, then push. |

## Upload and processing

| Symptom | Cause and fix |
|---|---|
| "Uploaded" but the build never appears | Processing failed, or it is still processing. Poll `/v1/builds` until `VALID`; a failure is explained only in an email to the uploader. |
| The submit step ran before processing finished | Nothing waited. `asc_submit.py` waits for `VALID` (`--wait-processing`). Typical time is 3 to 10 minutes. |
| The build is `VALID` but cannot be submitted: "Missing Compliance" | Export compliance unanswered. `--encryption-exempt`, or better `ITSAppUsesNonExemptEncryption` in Info.plist. |
| A background upload prints nothing until it ends | Output piped through `sed` or `tail`. Log to a file. |

## Submission

| Symptom | Cause and fix |
|---|---|
| "A review submission is already in progress" | An earlier submission, often a rejected one, is still open. Cancel it (`--replace-in-review`), wait for it to finish cancelling, then submit. |
| Draft submissions pile up in `READY_FOR_REVIEW` | Failed attempts leave empty drafts, and drafts cannot be deleted. They are harmless. Reuse one, as `asc_submit.py` does. |
| 500 errors when adding the version to a submission | Common for several minutes after a developer cancel. Retry every few minutes; do not create more drafts. |
| Submission fails although everything looks complete | A screenshot is still processing. Wait until every one is `COMPLETE`. |
| The version cannot be edited right after a cancel | Cancelling is asynchronous, and the version takes a few more seconds after it leaves the review state. Wait, then edit. |
| What's New is rejected on a first release | There is no What's New for version one. Leave it out. |
| An update is blocked by a missing What's New in one language | Every locale on the listing needs it. `--whats-new-all`. |
| Review notes will not save | Over 4000 characters. Subtitle is 30, promotional text 170, keywords 100. |
| Re-uploading screenshots doubled them | The upload appended. Delete the old set first. |

## In-app purchases

| Symptom | Cause and fix |
|---|---|
| The version went to review without its purchases | They were not in the same submission. First-time purchases must ride with a version. Cancel, add them, resubmit. |
| 409 "no pending version" when submitting a subscription | First subscriptions of an app: add the subscription group to the version's draft with "Add for Review" on the web. |
| Purchases are `READY_TO_SUBMIT` again | A cancelled or rejected submission releases them. Add them again. |
| A price change is refused or causes a rejection | The purchase is in review. Change prices before submitting or after approval. |
| A price cannot be set at all (409) | The purchase, or the app, has no availability yet. Set availability first. |
| A purchase is stuck in "Missing Metadata" | It lacks a localisation, a price, or a review screenshot; or the Paid Applications agreement is not active. |
| Rejected for a mismatch between the app and the notes | Purchase review notes still describe the old free limit or trial. Update them with the app. |

## Review

| Symptom | Cause and fix |
|---|---|
| Rejected, and the API shows nothing but the state | The message is only in the Resolution Center on the web. See rejections.md. |
| The reply box in the Resolution Center is gone | The submission was cancelled. Reply before cancelling; afterwards, put the answer in the review notes. |
| "Information Needed" (2.1) | A question, not a defect. Answer it in the thread and in the notes. If the honest answer is "no, the app does not have that", say so or add it; do not dodge. |
| An iPhone-only app was reviewed on an iPad | Normal. It must launch and work in compatibility mode. |

## After approval

| Symptom | Cause and fix |
|---|---|
| `READY_FOR_SALE` but not in the store, in any country | No availability record. Price and availability are separate. `asc_availability.py --apply`. |
| The lookup API returns nothing for a live app | `itunes.apple.com/lookup` lags, sometimes by more than a day. Check the store page. |
| Approved but not live | `releaseType` is `MANUAL`: the version is `PENDING_DEVELOPER_RELEASE` until released by hand. |
| Sales or download numbers cannot be read | Sales reports need the vendor number (Payments and Financial Reports), and analytics reports must be requested once and take about a day to appear. |

## Working from Windows

| Symptom | Cause and fix |
|---|---|
| An API path argument turns into `C:/Program Files/Git/v1/...` | Git Bash rewrites arguments that start with `/`. `asc_api.py` undoes it; for other tools set `MSYS_NO_PATHCONV=1`. |
| Backslashes vanish from a script written through a heredoc | Write files with an editor or a tool, not a heredoc, and use forward slashes in paths. |
| Values pasted into an SSH command carry a stray carriage return | Windows line endings in command output. `release_config.py env` prints Unix line endings for this reason. |
| A project file's every line shows as changed after an edit | The tool normalised line endings. `release_config.py` and `manual_sign.py` read and write bytes to avoid it. |
| `git push` over HTTPS hangs | A credential helper waiting on a window that never shows. Use SSH remotes or a token passed non-interactively. |

## Expo and React Native

| Symptom | Cause and fix |
|---|---|
| `expo prebuild` undid native changes | Prebuild regenerates `ios/`. Keep native changes in config plugins, and run prebuild before signing. |
| The iOS and Android numbers drifted | Keep `ios.buildNumber` and `android.versionCode` equal and add a test that says so. `bump` moves both when they were equal. |
| A library's native module adds a background mode or permission the store asks about | Read the merged Info.plist and entitlements after prebuild, not just `app.json`. Turn off what the app does not use with the library's plugin options. |
| `npm install` inside a workspace package broke the build | Install from the monorepo root. |

---
name: mobile-app
description: Take a mobile app from an idea to a store submission. Picks the stack (Expo / React Native, Swift, or Kotlin), builds the app with the bundled build skills, runs pre-submission checks (asc validate, asc review doctor, gplay preflight, play-policy-insights), submits to the App Store and Google Play with asc, gplay or EAS, and watches review status. Use when the user says "build me an app", "make a mobile app", "publish / ship / submit my app to the App Store or Play Store", "check my app before I submit", "will this get rejected", or asks how to get an app live.
license: MIT
---

# Mobile app: build, check, ship

You are the orchestrator. You do not replace the bundled skills: at each stage, load the skill named here and follow it. Skill names below are folder names in this pack. If the pack was installed as a Claude Code plugin, the same skills appear with the `mobile-app-skill:` prefix (for example `mobile-app-skill:asc-release-flow`).

The path is always the same: **intake -> pick the stack -> build -> store setup -> check -> ship -> watch review**. Do not skip the check stage.

## Rules that apply at every stage

1. **Say the limits before starting, once.** Read [references/limits.md](references/limits.md) and tell the user the ones that apply to them. The short version:
   - Apple Developer Program costs $99 a year. Google Play Console costs $25 once.
   - An iOS binary needs a Mac with Xcode, or a cloud build (EAS, paid plan limits apply).
   - New personal Google Play accounts must run a closed test with 12 testers for 14 days before production.
   - With `gplay`, the app's initial setup and first upload are manual steps in Play Console.
   - No tool, including this one, can guarantee approval. Apple and Google decide.
2. **Never promise approval, a review time, or a rejection-free submission.** Report the furthest state you verified and nothing past it.
3. **Dry-run before you mutate.** Every store-changing command gets its `--dry-run` first. Ask the user before adding `--confirm`, before any production release, and before cancelling a submission.
4. **Do not invent commands.** `asc` and `gplay` change often. Before running a command you have not seen in a bundled skill, load `asc-cli-usage` or `gplay-cli-usage` and check `asc <command> --help`, `asc search "<intent>"`, or `gplay <command> --help`.
5. **Secrets stay out of the repo.** API keys (`AuthKey_*.p8`), service-account JSON and keystores are never committed, printed or pasted into chat.

## Stage 0: Intake

Ask only what you cannot detect:

- What the app does, in one or two sentences, and the three screens that matter most.
- Platforms: iOS, Android, or both.
- The machine: macOS, Windows or Linux.
- Accounts: Apple Developer Program? Google Play Console? Personal or organisation? When was the Play account created?
- Is there existing code? Detect it: an `expo` dependency in `package.json` means Expo; an `.xcodeproj` or `.xcworkspace` means a native iOS project; a `build.gradle` or `build.gradle.kts` means a native Android project.

Then check the tools. Missing tools are fixed with [references/prerequisites.md](references/prerequisites.md).

```bash
asc version
asc auth status --validate
gplay --help
gplay auth doctor
```

## Stage 1: Pick the stack

Keep an existing project on the stack it already uses. For a new app:

| Situation | Stack | Reason |
|---|---|---|
| iOS and Android from one codebase, or no Mac, or no preference | Expo (React Native) | One codebase, and EAS can build the iOS binary in the cloud |
| iOS only, on a Mac with Xcode | Swift / SwiftUI | Native build, signing and upload run locally through `asc` |
| Android only | Kotlin / Jetpack Compose | Native build with Gradle, upload through `gplay` |

State the choice and the reason in one line, then move on.

## Stage 2: Build

Build the smallest version that does the one thing the user described. A store-ready app has no placeholder screens, no crashes on the main flow and no dead buttons. Apple says over 40% of unresolved review issues relate to guideline 2.1, App Completeness (crashes, placeholder content, incomplete information).

### Expo / React Native

1. Load `expo-overview` first. It routes to the right Expo skill and owns the shared setup rules.
2. Scaffold a new app with `npx create-expo-app@latest`, laid out per `expo-project-structure`.
3. Install packages with `npx expo install <pkg>`, not raw `npm` / `yarn` / `pnpm add`.
4. Use by task: `expo-router` (navigation), `expo-native-ui` (screens and styling), `expo-ui` (native controls), `expo-data-fetching` (network and caching), `expo-dev-client` (development builds), `expo-upgrade` (SDK upgrades).
5. For React Native beyond Expo: `react-native-best-practices` (performance), `react-navigation`, `upgrading-react-native`.

`expo-overview` also names Expo skills this pack does not bundle (for example `expo-animation`, `expo-design-system`, `eas-update`). If the task needs one, tell the user to add Expo's full pack: `npx skills@latest add expo/skills --skill '*'`.

### Swift / SwiftUI (Mac only)

1. None of the bundled skills scaffolds an Xcode project. Ask the user to create an empty iOS App project in Xcode, then work inside it.
2. Write views with `swiftui-expert-skill` and `swiftui-ui-patterns`. Use `swiftui-liquid-glass` for Liquid Glass and `swift-concurrency-expert` for concurrency errors.
3. Review the result with `swiftui-pro` before the check stage.
4. Compile-check without signing (from `asc-xcode-build`; replace the destination with a simulator installed on the host):

```bash
asc xcode build \
  --project "App.xcodeproj" \
  --scheme "App" \
  --destination "platform=iOS Simulator,name=iPhone 17 Pro Max,OS=27.0" \
  --no-code-signing \
  --output json
```

5. For a live simulator preview in the browser, load `rork-local`.

### Kotlin / Jetpack Compose

1. None of the bundled skills scaffolds an Android project. Ask the user to create one in Android Studio, then work inside it.
2. Use `navigation-3` (navigation), `edge-to-edge` (insets), `testing-setup` (tests), `migrate-xml-views-to-jetpack-compose` (old XML screens) and `r8-analyzer` (shrinking and keep rules).
3. Build the release bundle with `gplay-gradle-build`:

```bash
./gradlew bundleRelease
# Output: app/build/outputs/bundle/release/app-release.aab
```

## Stage 3: Store setup (once per app)

### iOS

1. Authenticate `asc` with an App Store Connect API key (full steps in [references/prerequisites.md](references/prerequisites.md)), then confirm with `asc auth status --validate`.
2. Register the bundle ID: `asc bundle-ids create --identifier "com.example.app" --name "My App" --platform IOS`.
3. Create the app record. There is no public API for this. Load `asc-app-create-ui` (browser automation with the user signed in), or have the user create it in App Store Connect.
4. Signing: load `asc-signing-setup`.
5. Resolve IDs with `asc-id-resolver`: `asc apps list --bundle-id "com.example.app"`.

### Android

1. Authenticate: `gplay setup --auto`, or `gplay auth login --service-account /path/to/service-account.json` if a key already exists. Confirm with `gplay auth doctor`.
2. Hand the user the manual Play Console steps. The `gplay` README says: "Initial public-app setup, first upload, ordinary Google-managed Play App Signing enrollment, and legal declarations still require a manual Play Console handoff."
3. If the Play account is a personal one created after 13 November 2023, start the closed test now (Stage 5). The 14 days are the slowest part of the whole process.

## Stage 4: Check (before every submission)

Run these and report every finding with its fix. Errors block the submission. Do not hide warnings.

### iOS

Load `asc-submission-health`.

```bash
asc validate --app "APP_ID" --version "1.0.0" --platform IOS --output table
asc review doctor --app "APP_ID" --version "1.0.0" --platform IOS --output table
```

- Add `--strict` to make warnings fail.
- Add `--deep` for App Privacy publication and agreements. It needs a web session first: `asc web auth login --apple-id "user@example.com"`.
- Fix listing text with `asc-metadata-sync`. Fix screenshots with `asc-screenshot-resize` (sizes) or `asc-shots-pipeline` (capture, frame, upload). Both rely on macOS tools.

### Android

Load `gplay-preflight`, then `gplay-submission-checks`.

```bash
# Offline. No credentials, no API calls.
gplay preflight --file app-release.aab --listings-dir ./metadata --fail-on error

# Needs auth. Readiness report against live track and listing state.
gplay validate --package com.example.app --bundle app-release.aab --track production --strict
```

Then load `play-policy-insights` (Google's own skill, needs `python3`) and present its compliance report. It audits three policy domains only: data safety, demo login credentials, and restricted permissions. If the app sells digital goods, also load `play-billing-library-version-upgrade`.

### What the tools do not check

These commands check that a submission is complete and that the binary is well formed. They do not judge how the app behaves against the App Review Guidelines or the full Play policy set. Before submitting, walk through the manual list in [references/limits.md](references/limits.md#manual-review-pass) with the user.

## Stage 5: Ship

### iOS from a Mac

Load `asc-xcode-build` to archive and export, then `asc-release-flow` to submit.

```bash
asc xcode archive --workspace "App.xcworkspace" --scheme "App" --configuration Release --clean \
  --archive-path ".asc/artifacts/App.xcarchive" \
  --xcodebuild-flag=-destination --xcodebuild-flag=generic/platform=iOS --output json

asc xcode export --archive-path ".asc/artifacts/App.xcarchive" --ipa-path ".asc/artifacts/App.ipa" \
  --xcodebuild-flag=-allowProvisioningUpdates --output json
```

Send it to TestFlight first (`asc-testflight-orchestration`), and install it on a real device:

```bash
asc publish testflight --app "APP_ID" --ipa ".asc/artifacts/App.ipa" --group "GROUP_ID" --wait
```

Then preview the App Store submission, show the plan to the user, and only then confirm:

```bash
asc publish appstore --app "APP_ID" --ipa ".asc/artifacts/App.ipa" --version "1.0.0" --submit --dry-run --output table
asc publish appstore --app "APP_ID" --ipa ".asc/artifacts/App.ipa" --version "1.0.0" --submit --wait --confirm
```

`rork-local` offers the same publish step from a local web UI. It is macOS only.

### iOS without a Mac (Expo)

Load `eas-app-stores`. EAS builds in the cloud; its costs and plan limits apply.

```bash
npx eas-cli@latest build -p ios --profile production --auto-submit
```

Once the build has finished processing in App Store Connect, run Stage 4, then submit the prepared version with `asc` (the `asc` binary runs on Windows):

```bash
asc review submit --app "APP_ID" --version "1.0.0" --build-number "45" --dry-run --output table
asc review submit --app "APP_ID" --version "1.0.0" --build-number "45" --confirm
```

### Android

Load `gplay-release-flow`. After the manual first upload, dry-run, then release to the internal track:

```bash
gplay release --package com.example.app --track internal --bundle app-release.aab --dry-run
gplay release --package com.example.app --track internal --bundle app-release.aab
```

For the closed test that new personal accounts need, load `gplay-testers-orchestration`. Testers are assigned inside an edit session, not with a flag on `gplay release`. The `alpha` track is the closed track.

When the account has production access and the user says go, promote with a staged rollout and manage it with `gplay-rollout-management`:

```bash
gplay promote --package com.example.app --from beta --to production --rollout 0.1
```

Expo projects can use `npx eas-cli@latest build -p android --profile production --auto-submit` instead (`eas-app-stores`).

## Stage 6: Watch review

### iOS

```bash
asc review status --app "APP_ID" --version "1.0.0" --platform IOS --output table

# Exits 0 when approved, 1 when rejected, 7 when still pending at the timeout.
asc status --app "APP_ID" --until review-done --timeout 2h --output json
```

- Apple says that on average 90% of submissions are reviewed in less than 24 hours. That is an average, not a promise.
- Rejected: load `asc-submission-health`, read the reason, fix the proven blocker, re-run Stage 4, then resubmit through `asc-release-flow`. Do not resubmit unchanged.
- Do not cancel a submission only because review is slow.
- A critical bug fix or a dated event: load `expedite-review`. It prepares the request the user files with Apple. Nothing here can speed up a review on its own.

### Android

Read the track state with `gplay tracks get --package com.example.app --track production`. Google says some reviews take up to 7 days or longer, and no published expedite process was found for Google Play.

## Stage 7: After approval

- Release notes: `app-store-changelog` (from git history) or `asc-whats-new-writer` (localised What's New).
- Android rollout: `gplay rollout update`, `gplay rollout halt`, `gplay rollout resume`, `gplay rollout complete` via `gplay-rollout-management`.
- Store listing updates: `asc-metadata-sync`, `gplay-metadata-sync`, `gplay-screenshot-automation`.
- Builds and retention: `asc-build-lifecycle`.

## Final report to the user

End every run with: the stack chosen and why; what was built; each check that ran with its result; each store command that mutated something; the furthest verified state per store (for example "uploaded to TestFlight, build processing" or "waiting for review"); what is waiting on the user (accounts, testers, manual Play Console steps); and the exact command to check status next.

## References

- [references/prerequisites.md](references/prerequisites.md): accounts, costs, installing `asc` and `gplay` on macOS and Windows, authentication.
- [references/limits.md](references/limits.md): what this cannot do, with the Apple, Google and Rork quotes and links, and the manual review pass.
- [references/skill-map.md](references/skill-map.md): every bundled skill by stage, with its upstream.

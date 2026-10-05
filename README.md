# Mobile App Skill

A skill pack for Claude Code that takes a mobile app from an idea to a store submission: it builds the app, checks it against the things that commonly get apps rejected, submits it to the App Store and Google Play, and watches the review. It is two skills by Deon Menezes (the `mobile-app` orchestrator and `expedite-review`) plus 48 open-source skills from the people who built the tools underneath.

```bash
npx skills add deonmenezes/mobile-app-skill
```

**Credit where it is due.** 48 of the 50 skills here were written by others and are copied unmodified under their own licences: [Rudrank Riyam](https://github.com/rudrankriyam) and [Rork](https://github.com/rorkai) (the `asc` CLI and its skills), [Omar Altamimi](https://github.com/tamtom) (the `gplay` CLI and its skills), [Expo](https://github.com/expo/skills), [Callstack](https://github.com/callstackincubator/agent-skills), [Antoine van der Lee](https://github.com/AvdLee/SwiftUI-Agent-Skill) and Omar Elsayed, [Thomas Ricouard](https://github.com/Dimillian/Skills), [Paul Hudson](https://github.com/twostraws/SwiftUI-Agent-Skill), and [Google's Android team](https://github.com/android/skills). Full list in [CREDITS.md](CREDITS.md).

This is an unofficial project. It is not affiliated with or endorsed by Apple, Google, Rork, Expo or anyone credited here.

## Contents

- [What you need before you start](#what-you-need-before-you-start)
- [Quick start](#quick-start)
- [Three ways to install](#three-ways-to-install)
- [What each stage does](#what-each-stage-does)
- [What it cannot do](#what-it-cannot-do)
- [Credits](#credits)
- [Licence](#licence)

## What you need before you start

- **Claude Code**, with a Pro, Max, Team, Enterprise or Console account. The free claude.ai plan does not include Claude Code.
- **An Apple Developer Program membership** to ship on iOS: $99 a year.
- **A Google Play Console account** to ship on Android: $25 once.
- **A Mac with Xcode, or a cloud build**, to produce an iOS app file. On Windows or Linux you can still build for iOS through Expo's EAS cloud builds, which have their own free and paid plans.
- **Node.js**, for `npx` and for Expo projects.
- **Time for the stores.** If your Google Play account is a personal one created after 13 November 2023, Google requires a closed test with 12 testers for 14 days before you can publish to production. Start that early.

Fees are as stated in [Rork's docs](https://docs.rork.com/introduction/deploy-your-app). Both store accounts have to be in your own name.

## Quick start

### 1. Install Claude Code

macOS, Linux or WSL:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Windows (PowerShell):

```powershell
irm https://claude.ai/install.ps1 | iex
```

Open a new terminal and run `claude --version` to confirm. More options are in the [Claude Code setup guide](https://code.claude.com/docs/en/setup).

### 2. Install this pack

```bash
npx skills add deonmenezes/mobile-app-skill
```

The installer lets you pick which skills to install and for which agent. Pick all of them, for Claude Code. To do that in one line, installed for every project on your machine:

```bash
npx skills add deonmenezes/mobile-app-skill --skill '*' -g -a claude-code
```

Two other ways to install are [further down](#three-ways-to-install).

### 3. Install the two store CLIs

`asc` talks to App Store Connect. `gplay` talks to Google Play Console. Install the one for each store you want to ship to.

**macOS**

```bash
# asc
brew install asc

# gplay
brew tap tamtom/tap
brew install tamtom/tap/gplay
```

**Windows (PowerShell)**

```powershell
# asc
winget install asc

# gplay
irm https://raw.githubusercontent.com/tamtom/play-console-cli/main/install.ps1 | iex
```

A note on `asc` for Windows: its README says the WinGet package is still being accepted, and "Until it appears in `winget search asc`, Windows users can download the signed release binaries directly from the GitHub releases page." If `winget install asc` finds nothing, download the file ending in `_windows_amd64.exe` from the [asc releases page](https://github.com/rorkai/App-Store-Connect-CLI/releases/latest), rename it to `asc.exe`, and put it in a folder on your `PATH`.

Without Homebrew on macOS or Linux, both tools have install scripts:

```bash
curl -fsSL https://asccli.sh/install | bash
curl -fsSL https://raw.githubusercontent.com/tamtom/play-console-cli/main/install.sh | bash
```

Then sign each one in, once:

```bash
# App Store Connect: create an API key at
# https://appstoreconnect.apple.com/access/integrations/api
asc auth login --name "MyApp" --key-id "ABC123" --issuer-id "DEF456" --private-key /path/to/AuthKey.p8 --network
asc auth status --validate

# Google Play: guided service-account setup
gplay setup --auto
gplay auth doctor
```

Keep the `.p8` key and the service-account JSON out of your project folder. Never commit them.

### 4. Say what app you want

Make an empty folder, open a terminal in it, run `claude`, and describe the app in plain words:

```text
/mobile-app I want a habit tracker for iPhone and Android. Three screens:
today's habits, a streak calendar, and settings.
```

If you installed the pack as a plugin, the command is `/mobile-app-skill:mobile-app`. You can also skip the command and just ask. Claude loads the skill when your request matches it.

Claude will ask a few questions (which platforms, which computer you are on, which accounts you have), pick a stack, and start building.

### 5. Ship

When the app works, tell Claude to ship it:

```text
Check the app and submit it to the App Store and Google Play.
```

Claude runs the pre-submission checks, shows you what it found, fixes what it can, shows you a dry run of the submission, and submits only after you say yes. Then it tells you how to check on the review.

## Three ways to install

All three install the same 50 skills.

### 1. The skills installer

```bash
npx skills add deonmenezes/mobile-app-skill
```

Uses the open [`skills` CLI](https://github.com/vercel-labs/skills). It works with Claude Code and other coding agents. Add `-g` to install for every project instead of just the current folder.

### 2. As a Claude Code plugin

Inside Claude Code, run these two commands:

```text
/plugin marketplace add deonmenezes/mobile-app-skill
/plugin install mobile-app-skill@deonmenezes
```

Plugin skills are namespaced, so the orchestrator becomes `/mobile-app-skill:mobile-app`.

### 3. By hand

Copy the folders inside `skills/` into `~/.claude/skills/`.

macOS or Linux:

```bash
git clone https://github.com/deonmenezes/mobile-app-skill.git
mkdir -p ~/.claude/skills
cp -r mobile-app-skill/skills/* ~/.claude/skills/
```

Windows (PowerShell):

```powershell
git clone https://github.com/deonmenezes/mobile-app-skill.git
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills" | Out-Null
Copy-Item -Recurse -Force mobile-app-skill\skills\* "$env:USERPROFILE\.claude\skills\"
```

## What each stage does

The `mobile-app` skill walks through these stages in order and loads the right skill at each one.

### Pick the stack

- **Expo (React Native)** if you want iOS and Android from one codebase, or you do not have a Mac.
- **Swift / SwiftUI** if you want iOS only and have a Mac with Xcode.
- **Kotlin / Jetpack Compose** if you want Android only.
- An existing project stays on the stack it already uses.

### Build

- Expo and React Native: `expo-overview`, `expo-project-structure`, `expo-router`, `expo-native-ui`, `expo-ui`, `expo-data-fetching`, `expo-dev-client`, `expo-upgrade`, `react-native-best-practices`, `react-navigation`, `upgrading-react-native`
- Swift: `swiftui-expert-skill`, `swiftui-ui-patterns`, `swiftui-liquid-glass`, `swift-concurrency-expert`, `swiftui-pro`
- Android: `navigation-3`, `edge-to-edge`, `testing-setup`, `migrate-xml-views-to-jetpack-compose`, `r8-analyzer`

### Store setup

Done once per app: sign the CLIs in, register the bundle ID, create the app record, set up signing.

- iOS: `asc-cli-usage`, `asc-id-resolver`, `asc-app-create-ui`, `asc-signing-setup`
- Android: `gplay-cli-usage`, plus a few steps you do yourself in Play Console

### Check

Run before every submission.

- iOS: `asc validate` and `asc review doctor` check that the submission is complete: build attached, metadata and screenshots, privacy policy URL, age rating, pricing, review contact details and demo login, leftover placeholder text. Skills: `asc-submission-health`, `asc-metadata-sync`, `asc-screenshot-resize`
- Android: `gplay preflight` scans the build file offline with nine scanners (manifest, permissions, native libraries, listing, leaked secrets, billing, privacy SDKs, policy, size). Google's own `play-policy-insights` audits data safety, demo login credentials and restricted permissions. Skills: `gplay-preflight`, `gplay-submission-checks`, `play-policy-insights`, `play-billing-library-version-upgrade`

### Ship

- iOS from a Mac: archive, export, upload to TestFlight, then submit. Skills: `asc-xcode-build`, `asc-build-lifecycle`, `asc-testflight-orchestration`, `asc-shots-pipeline`, `asc-release-flow`, `rork-local`
- iOS without a Mac, or any Expo project: cloud build and submit with EAS. Skill: `eas-app-stores`
- Android: build the bundle, release to a testing track, promote to production with a staged rollout. Skills: `gplay-gradle-build`, `gplay-release-flow`, `gplay-testers-orchestration`, `gplay-rollout-management`, `gplay-metadata-sync`, `gplay-screenshot-automation`
- Release notes: `app-store-changelog`, `asc-whats-new-writer`

### Watch the review

- `asc status --app "APP_ID" --until review-done --timeout 2h` waits for Apple's decision and reports approved, rejected or still pending.
- If the app is rejected, `asc-submission-health` reads the reason and routes the fix.
- `expedite-review` checks whether your situation fits Apple's criteria for an expedited review and drafts the request for you to file.

## What it cannot do

Read this part. It will save you a bad week.

**It cannot guarantee approval.** The checks catch incomplete submissions and many common technical problems. They do not judge how your app behaves, and Apple and Google make the final call. Even Rork's own hosted reviewer says of itself: "The reviewer is advisory. It never blocks a submission and it never promises an approval. Apple makes the final decision, and Apple's own review still takes days." ([Rork docs](https://docs.rork.com/ai-app-store-reviewer)) Google's `play-policy-insights` covers three policy areas, not all of them. The rules themselves are the [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/) and the [Play Developer Policy Center](https://play.google.com/about/developer-content-policy/).

**It cannot make a review faster.** Apple: "On average, 90% of submissions are reviewed in less than 24 hours." ([Apple](https://developer.apple.com/distribute/app-review/)) Google: "Certain apps may be subject to extended reviews, which may result in review times of up to 7 days or longer in exceptional cases." ([Google](https://support.google.com/googleplay/android-developer/answer/9859751)) Rork's guide puts a first App Store submission at 24 to 72 hours and adds: "Rejections are common and expected, especially on first submissions." ([Rork docs](https://docs.rork.com/appstore-submission-checklist/app-review-guide))

**It cannot expedite a review for you.** Apple accepts expedite requests in specific cases: "You can request the review of your app to be expedited if you face extenuating circumstances, such as fixing a critical bug in your app or releasing your app to coincide with an event you're directly associated with." ([Apple](https://developer.apple.com/distribute/app-review/)) You file the request yourself, signed in, at [Apple's form](https://developer.apple.com/contact/app-store/?topic=expedite). Apple decides whether to grant it. The `expedite-review` skill only helps you decide whether to ask and writes the text. Google Play has no published expedite process.

**It cannot skip Google's testing rule.** Google: "Developers with personal accounts created after November 13, 2023, must run a closed test for their app with a minimum of 12 testers who have been opted in continuously for at least 14 days." ([Google](https://support.google.com/googleplay/android-developer/answer/14151465)) A new personal account cannot go live on Google Play in a day.

**It cannot do your first Play Console steps.** From the `gplay` README: "Initial public-app setup, first upload, ordinary Google-managed Play App Signing enrollment, and legal declarations still require a manual Play Console handoff." ([gplay](https://github.com/tamtom/play-console-cli))

**It cannot build an iOS app on Windows by itself.** An iOS app file needs a Mac with Xcode or a cloud build such as EAS. The `asc` CLI itself runs on Windows, so checks, submission and status work there. `asc-xcode-build`, `asc-shots-pipeline`, `asc-screenshot-resize` and `rork-local` need a Mac.

**It cannot open your accounts.** Apple and Google both verify who you are. As Rork's docs say: "Start those early, because the waiting is the slow part, not the building." ([Rork docs](https://docs.rork.com/introduction/deploy-your-app))

**It is a snapshot.** The vendored skills are pinned to the commits listed in [CREDITS.md](CREDITS.md). `asc` and `gplay` move quickly. If a command fails, run it with `--help`, or install the newest skills straight from the upstream with `asc install-skills` and `gplay install-skills`.

## Credits

Two skills here are Deon's: `mobile-app` and `expedite-review`. Everything else is the work of:

| Creator | Work | Repository |
|---|---|---|
| Rudrank Riyam ([@rudrankriyam](https://github.com/rudrankriyam)) and Rork | `asc` CLI and 13 `asc-*` skills | [rorkai/app-store-connect-cli-skills](https://github.com/rorkai/app-store-connect-cli-skills), [rorkai/App-Store-Connect-CLI](https://github.com/rorkai/App-Store-Connect-CLI) |
| Rork | `rork-local` | [rorkai/rork-local](https://github.com/rorkai/rork-local) |
| Omar Altamimi ([@tamtom](https://github.com/tamtom)) | `gplay` CLI and 9 `gplay-*` skills | [tamtom/gplay-cli-skills](https://github.com/tamtom/gplay-cli-skills), [tamtom/play-console-cli](https://github.com/tamtom/play-console-cli) |
| Expo (650 Industries) | 9 Expo and EAS skills | [expo/skills](https://github.com/expo/skills) |
| Callstack | 3 React Native skills | [callstackincubator/agent-skills](https://github.com/callstackincubator/agent-skills) |
| Antoine van der Lee ([@AvdLee](https://github.com/AvdLee)) and Omar Elsayed | `swiftui-expert-skill` | [AvdLee/SwiftUI-Agent-Skill](https://github.com/AvdLee/SwiftUI-Agent-Skill) |
| Thomas Ricouard ([@Dimillian](https://github.com/Dimillian)) | 4 Swift and App Store skills | [Dimillian/Skills](https://github.com/Dimillian/Skills) |
| Paul Hudson ([@twostraws](https://github.com/twostraws)) | `swiftui-pro` | [twostraws/SwiftUI-Agent-Skill](https://github.com/twostraws/SwiftUI-Agent-Skill) |
| Google (Android) | 7 Android and Play skills | [android/skills](https://github.com/android/skills) |
| Evan Bacon ([@EvanBacon](https://github.com/EvanBacon)) | `serve-sim`, used by `rork-local` | [EvanBacon/serve-sim](https://github.com/EvanBacon/serve-sim) |

Worth installing alongside this pack, linked rather than copied because they carry no licence file or are hosted products:

- [Software Mansion's skills](https://github.com/software-mansion-labs/skills) for React Native animations and gestures
- [Vercel's agent skills](https://github.com/vercel-labs/agent-skills), which include `react-native-skills`
- [Axiom](https://github.com/CharlesWiltgen/Axiom) by Charles Wiltgen, a large set of Apple-platform skills (MIT, too big to bundle)
- [Rork](https://rork.com), the hosted app builder, and its [AI App Store Reviewer](https://rork.com/app-store-reviewer)

Every vendored skill, its licence and the exact commit it was copied from are listed in [CREDITS.md](CREDITS.md). Licence texts are in [THIRD_PARTY_LICENSES](THIRD_PARTY_LICENSES). If you find one of these skills useful, go and star the creator's repository.

## Not affiliated

This is an unofficial, community project. It is not affiliated with, endorsed by, or sponsored by Apple, Google, Rork, Expo, Callstack, Anthropic, or any person or organisation credited above. App Store, TestFlight, Google Play and other product names belong to their owners and are used here only to say what the skills work with. The `asc` and `gplay` CLIs are themselves unofficial tools.

## Licence

Deon's own files are MIT licensed, Copyright (c) 2026 Deon Menezes. See [LICENSE](LICENSE). Vendored skills remain under their own licences (MIT or Apache-2.0); see [CREDITS.md](CREDITS.md), [NOTICE](NOTICE) and [THIRD_PARTY_LICENSES](THIRD_PARTY_LICENSES).

Made by Deon Menezes ([@deon_tech](https://www.instagram.com/deon_tech/) on Instagram, [@deonmenezes](https://github.com/deonmenezes) on GitHub).

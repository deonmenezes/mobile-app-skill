# Prerequisites

What the user needs before anything can reach a store, and how to install the two CLIs this skill drives. Commands are copied from the upstream READMEs named beside them.

## Accounts and costs

| Need | Cost | Notes |
|---|---|---|
| Apple Developer Program membership | $99 a year | Required to ship on the App Store or TestFlight |
| Google Play Console account | $25 once | Identity verification applies. New personal accounts must also run a closed test (see below) |
| Claude Code account | Pro, Max, Team, Enterprise or Console | The free claude.ai plan does not include Claude Code |
| EAS (optional) | Free tier and paid plans | Only if iOS or Android builds run in Expo's cloud. See https://expo.dev/pricing |

Fees as stated in Rork's docs: "Apple charges $99 a year, Google charges $25 once." (https://docs.rork.com/store-guides/google-play-developer-account)

Start both store accounts first. Rork's docs put it this way: "Start those early, because the waiting is the slow part, not the building." (https://docs.rork.com/introduction/deploy-your-app)

## Machine

| Task | macOS | Windows / Linux |
|---|---|---|
| Write the app with Claude Code | yes | yes |
| Build an Android `.aab` | yes | yes |
| Build an iOS `.ipa` locally (Xcode) | yes | no |
| Build an iOS `.ipa` in the cloud (EAS) | yes | yes |
| Run `asc` (validate, submit, status) | yes | yes |
| Run `gplay` | yes | yes |
| `asc-xcode-build`, `asc-shots-pipeline`, `asc-screenshot-resize`, `rork-local` | yes | no |

## Install `asc` (App Store Connect CLI)

Source: https://github.com/rorkai/App-Store-Connect-CLI (README, "Install").

macOS:

```bash
# Homebrew (recommended)
brew install asc

# Install script (macOS/Linux)
curl -fsSL https://asccli.sh/install | bash
```

Windows (PowerShell):

```powershell
# WinGet
winget install --id Rorkai.ASC --exact
```

Use the exact id: plain `winget install asc` matches more than one package and stops. Without WinGet, the signed release binaries are at https://github.com/rorkai/App-Store-Connect-CLI/releases/latest. Download the asset whose name ends in `_windows_amd64.exe` (for example `asc_5.10.0_windows_amd64.exe`), check it against the checksums file published in the same release (`asc_5.10.0_checksums.txt`), rename it to `asc.exe`, and put it in a folder on `PATH`.

Confirm it works:

```bash
asc version
asc --help
```

### Authenticate `asc`

Generate an API key at https://appstoreconnect.apple.com/access/integrations/api, then:

```bash
asc auth login \
  --name "MyApp" \
  --key-id "ABC123" \
  --issuer-id "DEF456" \
  --private-key /path/to/AuthKey.p8 \
  --network
```

Individual API keys have no issuer ID. Omit `--issuer-id` and pass `--key-type individual`.

Check it:

```bash
asc auth status --validate
asc auth doctor
asc apps list --output table
```

If keychain access is blocked, re-run `asc auth login` with `--bypass-keychain`.

## Install `gplay` (Google Play Console CLI)

Source: https://github.com/tamtom/play-console-cli (README, "Install").

macOS:

```bash
# Homebrew (recommended)
brew tap tamtom/tap
brew install tamtom/tap/gplay

# Standalone binary, macOS/Linux
curl -fsSL https://raw.githubusercontent.com/tamtom/play-console-cli/main/install.sh | bash
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/tamtom/play-console-cli/main/install.ps1 | iex
```

### Authenticate `gplay`

`gplay` authenticates to Google Play with a service account.

```bash
# One-command setup: installs gcloud if needed, creates the service account,
# and opens Play Console for the one manual step (granting access)
gplay setup --auto

# Or, with an existing service-account key
gplay auth login --service-account /path/to/service-account.json

# Verify
gplay auth doctor
```

Manual setup, if `gplay setup --auto` is not an option: create a Google Cloud project, enable the "Google Play Android Developer API", create a service account and a JSON key, then in Play Console go to Users and permissions, invite the service-account email and grant access. The `gplay` README lists each click.

## EAS CLI (Expo projects only)

From the bundled `eas-app-stores` skill:

```bash
npm install -g eas-cli
eas login
npx eas-cli@latest init
```

Check login with `eas whoami`.

## Google's closed-testing gate

Google: "Developers with personal accounts created after November 13, 2023, must run a closed test for their app with a minimum of 12 testers who have been opted in continuously for at least 14 days." (https://support.google.com/googleplay/android-developer/answer/14151465)

Plan for it on day one: collect 12 tester email addresses or a Google Group while the app is still being built.

## Keep secrets out of the project

- Store `AuthKey_*.p8`, service-account JSON and keystores outside the repository, or add them to `.gitignore` before the first commit.
- `gplay preflight` includes a `secrets` scanner that flags keys shipped inside a build. Run it before every upload.

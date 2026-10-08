# Build hosts

An iOS archive needs macOS and Xcode. Everything else in a release (bump, upload, submit, watch) runs anywhere. This page covers the two places the archive can happen and how to get code to them.

## A Mac over SSH

The usual setup: the work happens on another machine (often Windows), and a Mac on the same network or VPN does the builds.

### Reach it

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 me@my-mac true
```

- `BatchMode=yes` makes a missing key fail at once instead of hanging on a password prompt.
- A timeout means the Mac is asleep, off, or off the network. A laptop with its lid shut sleeps whatever its settings say, unless it is on power with an external display or sleep has been disabled. Fall through to the next host; do not loop.
- A VPN address (for example Tailscale) works from anywhere. A LAN address is faster for large pushes when both machines are at home.
- If the Mac supports it, wake-on-LAN from another device on its network can wake it. This only works on AC power and often not over Wi-Fi.

### Get the code there

Pushing straight to the Mac avoids a round trip through a hosting service and works when the Mac has no credentials for it.

```bash
# once, on the Mac checkout:
git config receive.denyCurrentBranch updateInstead
# once, on the working machine:
git remote add mac ssh://me@my-mac/Users/me/Projects/example
# every release:
git push mac HEAD:refs/heads/release-branch
```

- `updateInstead` refuses the push when the Mac's working tree is dirty. That is a feature. If it is dirty with leftovers from an earlier build, `git stash -u` on the Mac and push again.
- Both trees should be clean before a release build: uncommitted changes on the working machine do not reach the Mac, and the release would not match the commit.
- Files that are gitignored but needed to build (a secrets file, downloaded model weights, `GoogleService-Info.plist`) must already be on the Mac. List them in the repository's README so a fresh checkout or a CI runner can be given them.

### Get the scripts there

```bash
ssh me@my-mac 'mkdir -p ~/.cache/app-store-release/profiles'
scp <skill>/scripts/* me@my-mac:~/.cache/app-store-release/
```

Copy the files, not the folder: `scp -r scripts host:dir` nests a `scripts/` folder inside an existing directory, and later releases would keep running the first copy.

`mac_release.sh` needs `manual_sign.py` beside it. Neither needs anything installed beyond Xcode's command line tools.

### Run it

```bash
ENV="$(python scripts/release_config.py env | tr '\n' ' ') ASC_KEY_ID=XXXX ASC_ISSUER_ID=xxxx ASC_PRIVATE_KEY_PATH=~/.appstoreconnect/AuthKey_XXXX.p8"

ssh me@my-mac "$ENV bash ~/.cache/app-store-release/mac_release.sh check"
ssh me@my-mac "nohup env $ENV bash ~/.cache/app-store-release/mac_release.sh upload > ~/release.log 2>&1 &"
ssh me@my-mac "tail -5 ~/release.log"     # poll until MAC_RELEASE_OK or MAC_RELEASE_FAILED
```

- Run the real build under `nohup` and poll. A dropped SSH session kills a foreground build half way through an archive.
- A pipe such as `| tail -25` on the build command hides the "uploaded" line and buffers everything until the end. Log to a file and read the file.
- The Mac's login shell is usually zsh. `mac_release.sh` starts with `#!/bin/bash` and is run with `bash`, so its behaviour does not depend on the login shell. Anything typed ad hoc over SSH does: unquoted variables do not word-split in zsh.

### What `mac_release.sh` does, and why

| Step | Why |
|---|---|
| `check`: disk, power, certificate, profiles, API key | Fails in seconds instead of after a full archive. A Mac under 20% on battery is refused. |
| Build lock in `/tmp` | Two archives at once exhaust memory and one dies without an error. A lock whose process is gone is taken over. |
| Throwaway keychain from the `.p12` | The login keychain is locked in an SSH session, and codesign fails with "User interaction is not allowed" or `errSecInternalComponent`. The keychain is deleted and the keychain list restored on exit, including on Ctrl-C. |
| `manual_sign.py` on the project file | Automatic signing wants a development certificate and an unlocked keychain. Manual signing is set per target, by bundle id; a tracked project file is put back afterwards. |
| `PREBUILD` before signing | `xcodegen generate` and `expo prebuild` rewrite the project, which would undo the signing change if they ran after it. Never run them while an archive is in progress either. |
| Version check on the archive | A generated project can reset to 1.0 (1). Uploading that wastes a build number and a review. |
| Bare `PATH` for `-exportArchive` | Homebrew's `rsync` ahead of Apple's breaks the export with "Copy failed". |
| `-jobs` cap | On 16 GB the Swift compiler can be killed for memory with no useful message. `JOBS=2` is slower and finishes. |
| Upload with API-key flags on `xcodebuild` | No Apple ID session, no altool, no Transporter. |

### Provisioning profiles

The Mac needs each profile named in `signing.profiles` installed. Fetch them where Python and the API key are, then hand them over:

```bash
python scripts/release_config.py profile-names | tr '\n' '\0' | xargs -0 python scripts/fetch_profiles.py --out profiles
scp profiles/*.mobileprovision me@my-mac:~/.cache/app-store-release/profiles/
# then add  PROFILE_DIR=~/.cache/app-store-release/profiles  to the environment of mac_release.sh
```

Profiles are snapshots. After adding a capability or an App Group to an App ID, regenerate the profile and fetch it again, or the archive is signed without it. `fetch_profiles.py` prints the App Groups each profile carries; check that line.

### The certificate

Export the Apple Distribution certificate with its private key from Keychain Access as a `.p12`, once, on a Mac where it is installed. Store it and a one-line password file under `~/.appstoreconnect/signing/` on the build Mac, readable only by the user. A team can hold only a small number of distribution certificates, so share one `.p12` between hosts instead of creating one per machine.

## GitHub Actions (cloud fallback)

`templates/ios-release.yml` runs the same `mac_release.sh` on a GitHub-hosted Mac. Use it when the Mac does not answer, or always.

### One-time setup per repository

1. Copy `templates/ios-release.yml` to `.github/workflows/ios-release.yml` and push it to the default branch (a workflow can only be started by hand once it exists there). Pushing workflow files needs a token with the `workflow` scope.
2. Set five secrets:

```bash
gh secret set ASC_KEY_ID        --repo me/example --body "XXXXXXXXXX"
gh secret set ASC_ISSUER_ID     --repo me/example --body "xxxxxxxx-...."
gh secret set ASC_PRIVATE_KEY   --repo me/example < AuthKey_XXXXXXXXXX.p8
base64 -w0 distribution.p12 | gh secret set DIST_P12_BASE64 --repo me/example      # macOS: base64 -i file
gh secret set DIST_P12_PASSWORD --repo me/example --body "the-password"
```

3. Add steps for anything the build needs that is not in the repository: gitignored secrets files (write them from further secrets), `brew install xcodegen`, `npm ci`, model downloads.
4. Run it once with `mode=archive` and read the log before trusting it with `upload`.

Storing a signing certificate and an API key as repository secrets is a real exposure: anyone who can push a workflow to that repository can use them. Do it only on repositories the user controls, ask before doing it, and prefer a key with the App Manager role over Admin.

### Each release

```bash
git push origin release-branch
gh workflow run ios-release.yml --repo me/example --ref release-branch -f mode=upload
gh run watch --repo me/example            # or: gh run list --workflow ios-release.yml --limit 1
```

On failure the logs are in the run's artifact (`archive.log`, `export.log`).

- Hosted runners start cold: no DerivedData, no resolved packages. Expect a build several times slower than a warm Mac.
- Mac minutes on private repositories are metered at a higher rate than Linux minutes. Check the plan before making the cloud the default.
- The Xcode version on the runner image changes over time. If the app needs a specific one, add `sudo xcode-select -s /Applications/Xcode_XX.app` before the build step.

## An IPA and no Mac

If a Mac built the `.ipa` but cannot finish (it is about to sleep, or its upload keeps failing), copy the file off it in one go and upload from anywhere:

```bash
ssh me@my-mac "... bash ~/.cache/app-store-release/mac_release.sh ipa"     # prints MAC_RELEASE_OK ipa <path>
scp me@my-mac:<path> ./App.ipa
python scripts/upload_ipa.py App.ipa APP_ID --dry-run
python scripts/upload_ipa.py App.ipa APP_ID --wait 20
```

`upload_ipa.py` refuses an IPA whose bundle id is not the app's, and a build number that already exists.

## Expo's cloud builds

For an Expo app with no Mac at all, EAS builds and submits in Expo's cloud. That path is the `eas-app-stores` skill in this pack. After EAS has uploaded a build, step 5 onward of this skill (submit, watch, verify) applies unchanged.

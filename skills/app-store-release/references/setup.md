# Setup

Done once per app. After it, a release needs no questions.

## 1. Credentials (once per Apple team)

Create an App Store Connect API key at https://appstoreconnect.apple.com/access/integrations/api with the **App Manager** role (Admin if the scripts should also manage certificates and profiles). Download the `.p8` once; Apple does not offer it again.

Put the key outside every repository and write a profile file:

```
~/.config/appstoreconnect/AuthKey_XXXXXXXXXX.p8
~/.config/appstoreconnect/credentials.env
```

```
ASC_KEY_ID=XXXXXXXXXX
ASC_ISSUER_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ASC_PRIVATE_KEY_PATH=~/.config/appstoreconnect/AuthKey_XXXXXXXXXX.p8
```

Check it: `python scripts/asc_api.py apps` lists the team's apps.

- A second Apple team gets its own file, for example `clientteam.env`, used with `--profile clientteam` and `credentials_profile` in that app's config. A key never sees another team's apps.
- Environment variables with the same names override the file. `ASC_PRIVATE_KEY` (the key's contents) is accepted in place of the path, for CI.
- An individual API key has no issuer id: leave `ASC_ISSUER_ID` out. The Python scripts accept that (not exercised). `mac_release.sh upload` needs a team key with an issuer id; with an individual key, build with `mac_release.sh ipa` and upload with `upload_ipa.py`.
- The Mac that builds needs the same three values to upload. Keep its copy of the `.p8` under `~/.appstoreconnect/` there.

## 2. The config file

`python scripts/release_config.py init` writes `.asc/release.json` in the app's repository. Commit it. It contains no secrets.

```json
{
  "app_id": "1234567890",
  "bundle_id": "com.example.app",
  "team_id": "ABCDE12345",
  "credentials_profile": "credentials",
  "project": {
    "kind": "xcodegen",
    "workspace": null,
    "xcodeproj": "Example.xcodeproj",
    "scheme": "Example",
    "prebuild": "xcodegen generate"
  },
  "signing": {
    "p12": "~/.appstoreconnect/signing/distribution.p12",
    "p12_password_file": "~/.appstoreconnect/signing/distribution.p12.password",
    "profiles": {
      "com.example.app": "Example AppStore",
      "com.example.app.widget": "Example Widget AppStore"
    }
  },
  "build": {
    "hosts": ["mac", "github"],
    "mac": {"ssh": "me@my-mac", "dir": "~/Projects/example", "git_remote": "mac"},
    "github": {"repo": "me/example", "workflow": "ios-release.yml"},
    "jobs": null
  },
  "release": {
    "release_type": "AFTER_APPROVAL",
    "phased": false,
    "encryption_exempt": true,
    "whats_new": "fastlane/metadata/en-US/release_notes.txt",
    "review_notes": null,
    "with_iaps": false
  },
  "autonomy": "submit",
  "rejections": "browser"
}
```

| Field | Where it comes from |
|---|---|
| `app_id` | `asc_api.py apps` (the first column). The app record must already exist. |
| `bundle_id`, `project.*` | Detected by `init`. Check them. For Expo, fill `workspace` and `scheme` after the first prebuild. |
| `team_id` | The `team` column of `fetch_profiles.py --list`. |
| `signing.profiles` | One App Store profile per bundle id that is signed: the app and every extension. `fetch_profiles.py --list` shows each profile's bundle id and name; pick the `ACTIVE` `IOS_APP_STORE` ones. |
| `signing.p12`, `p12_password_file` | Paths **on the build Mac**: the Apple Distribution certificate exported as `.p12`, and a one-line file with its password. |
| `build.mac.git_remote` | A git remote that points at the Mac checkout, if code is pushed straight to the Mac. See build-hosts.md. |
| `build.jobs` | Set to `2` if the Mac has 16 GB of memory and archives die without an error. |
| `project.version_files` | Only for `"kind": "custom"`: `[{"path": "...", "version": "regex", "build": "regex"}]`, one capture group each. |

`release_config.py show` prints the config, the current version and build, and what is still missing.

## Questions to ask

Ask these once, in one go, and write the answers into the config. Detect everything else. Give the recommended answer first.

1. **How far should a release go without asking?** (`autonomy`)
   - `submit` (recommended for a solo developer): bump, build, upload, check, submit for review, release on approval. Stops for blockers, rejections, and before cancelling anything in review.
   - `testflight`: stop once the build is on TestFlight; submit when told.
   - `ask`: confirm every upload and submission.
2. **Where do builds run?** (`build.hosts`, in order)
   - `["mac", "github"]` (recommended when the Mac is a laptop): the Mac when it answers, a GitHub-hosted Mac when it does not.
   - `["mac"]`: only the user's Mac. Releases wait when it is asleep.
   - `["github"]`: always the cloud. Slower cold builds; private repositories have a limited free allowance of Mac minutes.
   Then, for `mac`: the SSH address, the checkout path on the Mac, and where the `.p12` and its password file are.
3. **How should a rejection be read?** (`rejections`) Apple's API does not return the reviewer's message.
   - `browser` (recommended): read the Resolution Center in a browser the user is signed in to.
   - `paste`: tell the user it was rejected and wait for them to paste the message.
   - `email`: read Apple's notification mail. It names the guideline but usually not the detail.
4. **When should an approved version go live?** (`release.release_type`)
   - `AFTER_APPROVAL` (recommended): as soon as Apple approves.
   - `MANUAL`: the user presses Release. Needed for a launch tied to a date.
   And: phased rollout over 7 days, yes or no (`release.phased`, default no).
5. **Does the app use encryption beyond HTTPS and Apple's own APIs?** (`release.encryption_exempt`) Almost always no, which is `true` here. If the user is unsure, say that this is a legal declaration and point them to Apple's export compliance page rather than answering for them.
6. **Does the app sell in-app purchases or subscriptions that have never been reviewed?** If yes, set `release.with_iaps` for the next release and read the in-app purchase notes in SKILL.md.

Do not ask about things the tools can read: the bundle id, the scheme, the current version, the profile names, the team.

## 3. One-time checks before the first automated release

- `python scripts/asc_status.py APP_ID` runs clean.
- `mac_release.sh check` passes on the Mac (certificate, profiles, power, disk).
- The app's Info.plist sets `ITSAppUsesNonExemptEncryption`, so no build ever waits on the export compliance question.
- For the cloud fallback: the workflow file is in the repository and its five secrets are set (build-hosts.md).
- The first release through these scripts is watched by a person.

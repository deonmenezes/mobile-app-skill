#!/bin/bash
# Archive, sign and upload an iOS app on a Mac that nobody is logged in to: over SSH, or on a CI runner.
#
#   bash mac_release.sh check     tools, power, disk, certificate, profiles, API key. Builds nothing.
#   bash mac_release.sh archive   signed Release archive only
#   bash mac_release.sh ipa       archive, then export an .ipa (upload it later with upload_ipa.py)
#   bash mac_release.sh upload    archive, then export and upload to App Store Connect
#
# Settings come from the environment. `release_config.py env` prints most of them from .asc/release.json.
#   PROJECT_DIR          the checkout to build                       (required)
#   SCHEME               Xcode scheme                                (required)
#   TEAM_ID              Apple team id                               (required)
#   PROFILES             "bundle.id=Profile Name;bundle.id.ext=Other Profile"   (required)
#   WORKSPACE or XCODEPROJ   relative to PROJECT_DIR                 (one is required)
#   P12, P12_PASSWORD_FILE   distribution certificate and a file holding its password (required)
#   PREBUILD             command that generates the Xcode project: "xcodegen generate", "npx expo prebuild --platform ios"
#   APP_VERSION, APP_BUILD   expected numbers; the archive is refused if it carries others
#   PROFILE_DIR          folder of *.mobileprovision files to install first (from fetch_profiles.py)
#   ASC_KEY_ID, ASC_ISSUER_ID, ASC_PRIVATE_KEY_PATH   App Store Connect team API key, for `upload`
#   JOBS                 cap parallel compile jobs (2 keeps a 16 GB Mac from killing the Swift compiler)
#   OUT_DIR              where the archive, IPA and logs go (default ~/Library/Caches/app-store-release/<scheme>)
#
# The last line printed is MAC_RELEASE_OK <mode> or MAC_RELEASE_FAILED <step>.
# Written for the bash 3.2 that ships with macOS.
set -uo pipefail
MODE=${1:-check}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH   # non-interactive shells do not get the Homebrew PATH
export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8          # without these, tools choke on non-ASCII release notes

fail() { echo "ERROR: $2"; echo "MAC_RELEASE_FAILED $1"; exit 1; }
expand() { echo "${1/#\~/$HOME}"; }
xml() { sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' <<< "$1"; }

for v in PROJECT_DIR SCHEME TEAM_ID PROFILES P12 P12_PASSWORD_FILE; do
  [ -n "${!v:-}" ] || fail config "$v is not set"
done
[ -n "${WORKSPACE:-}${XCODEPROJ:-}" ] || fail config "set WORKSPACE or XCODEPROJ"
PROJECT_DIR=$(expand "$PROJECT_DIR"); P12=$(expand "$P12"); P12_PASSWORD_FILE=$(expand "$P12_PASSWORD_FILE")
OUT=$(expand "${OUT_DIR:-$HOME/Library/Caches/app-store-release/$SCHEME}")
ARCHIVE="$OUT/$SCHEME.xcarchive"
mkdir -p "$OUT"
cd "$PROJECT_DIR" || fail config "PROJECT_DIR $PROJECT_DIR does not exist"

# ---------------------------------------------------------------- preflight
profile_name() { security cms -D -i "$1" 2>/dev/null | plutil -extract Name raw - 2>/dev/null; }
PROFILE_HOMES=("$HOME/Library/Developer/Xcode/UserData/Provisioning Profiles" "$HOME/Library/MobileDevice/Provisioning Profiles")

preflight() {
  local bad=0
  command -v xcodebuild >/dev/null || fail check "xcodebuild not found"
  echo "host:     $(sw_vers -productVersion 2>/dev/null), $(xcodebuild -version 2>/dev/null | tr '\n' ' ')"
  echo "checkout: $(git rev-parse --abbrev-ref HEAD 2>/dev/null) $(git rev-parse --short HEAD 2>/dev/null), $(git status --short 2>/dev/null | wc -l | tr -d ' ') uncommitted file(s)"
  local free; free=$(df -g "$HOME" | awk 'NR==2 {print $4}')
  echo "disk:     ${free} GB free"
  [ "${free:-0}" -ge 10 ] || { echo "  !! under 10 GB free: an archive can fail half way"; bad=1; }
  local batt; batt=$(pmset -g batt 2>/dev/null)
  if echo "$batt" | grep -q "Battery Power"; then
    local pct; pct=$(echo "$batt" | grep -Eo '[0-9]+%' | head -1 | tr -d '%')
    echo "power:    on battery, ${pct}%"
    [ "${pct:-100}" -ge 20 ] || { echo "  !! under 20% and not charging: plug the Mac in first"; bad=1; }
  else
    echo "power:    on AC"
  fi
  [ -f "$P12" ] || { echo "  !! certificate not found: $P12"; bad=1; }
  [ -f "$P12_PASSWORD_FILE" ] || { echo "  !! certificate password file not found: $P12_PASSWORD_FILE"; bad=1; }

  # Xcode 16+ looks in the first folder, older Xcode in the second. Install into both, named <uuid>.mobileprovision.
  local home f
  if [ -n "${PROFILE_DIR:-}" ]; then
    for home in "${PROFILE_HOMES[@]}"; do
      mkdir -p "$home" && cp "$(expand "$PROFILE_DIR")"/*.mobileprovision "$home"/ 2>/dev/null
    done
  fi
  local installed=""
  for home in "${PROFILE_HOMES[@]}"; do
    for f in "$home"/*.mobileprovision; do
      [ -f "$f" ] && installed+="$(profile_name "$f")"$'\n'
    done
  done
  local pair name
  while IFS= read -r pair; do
    [ -n "$pair" ] || continue
    name=${pair#*=}
    if grep -Fxq "$name" <<< "$installed"; then echo "profile:  $name"; else echo "  !! profile not installed: $name (fetch_profiles.py, then PROFILE_DIR)"; bad=1; fi
  done <<< "$(tr ';' '\n' <<< "$PROFILES")"

  if [ "$MODE" = upload ]; then
    for v in ASC_KEY_ID ASC_ISSUER_ID ASC_PRIVATE_KEY_PATH; do
      [ -n "${!v:-}" ] || { echo "  !! $v is not set (needed to upload)"; bad=1; }
    done
    [ -z "${ASC_PRIVATE_KEY_PATH:-}" ] || [ -f "$(expand "$ASC_PRIVATE_KEY_PATH")" ] || { echo "  !! API key file not found: $ASC_PRIVATE_KEY_PATH"; bad=1; }
  fi
  return $bad
}

preflight || fail check "fix the items marked !! above"
if [ "$MODE" = check ]; then echo "MAC_RELEASE_OK check"; exit 0; fi
case "$MODE" in archive|ipa|upload) ;; *) fail config "unknown mode $MODE";; esac

# ------------------------------------------------- one build at a time, cleanup
# Two archives at once exhaust memory. The lock records its owner's pid and is taken over only when that process is gone.
LOCK=/tmp/app-store-release.lock
until mkdir "$LOCK" 2>/dev/null; do
  holder=$(head -1 "$LOCK/pid" 2>/dev/null)
  if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
    echo "waiting for another build to finish ($(cat "$LOCK/owner" 2>/dev/null))"; sleep 20
  elif [ -z "$holder" ] && [ -z "$(find "$LOCK" -maxdepth 0 -mmin +1 2>/dev/null)" ]; then
    sleep 2   # just created by another run that has not written its pid yet
  else
    rm -rf "$LOCK" || fail lock "cannot remove the stale lock $LOCK (owned by another user?)"
  fi
done
echo $$ > "$LOCK/pid"
echo "$SCHEME $MODE, pid $$, since $(date +%H:%M:%S)" > "$LOCK/owner"

KC="$HOME/Library/Keychains/app-store-release-$$.keychain-db"
KCPW=$(uuidgen)
# The user's keychain search list, minus leftovers of a run that was killed outright. Kept as an array: paths can hold spaces.
ORIGINAL_KEYCHAINS=()
while IFS= read -r kc; do
  [ -n "$kc" ] && ORIGINAL_KEYCHAINS+=("$kc")
done < <(security list-keychains -d user | sed -e 's/^ *"//' -e 's/"$//' | grep -v '/app-store-release-[0-9]*\.keychain-db$')
PBX=""; PBX_BACKUP=""; CHILD=""
cleanup() {
  # With nothing recorded (the listing failed), leave the search list alone rather than clear it.
  [ ${#ORIGINAL_KEYCHAINS[@]} -eq 0 ] || security list-keychains -d user -s "${ORIGINAL_KEYCHAINS[@]}"
  security delete-keychain "$KC" 2>/dev/null
  [ ! -f "$PBX_BACKUP" ] || mv -f "$PBX_BACKUP" "$PBX"   # leave a tracked project file as it was
  rm -rf "$LOCK"
}
trap cleanup EXIT
# bash runs a trap only after the foreground command ends, so long commands run in the background under `wait`,
# which a signal interrupts at once. The child is then stopped and `exit` runs the EXIT trap.
trap '[ -z "$CHILD" ] || { pkill -P "$CHILD" 2>/dev/null; kill "$CHILD" 2>/dev/null; }; exit 130' HUP INT TERM
run() { "$@" & CHILD=$!; wait "$CHILD"; local rc=$?; CHILD=""; return $rc; }

# ------------------------------------------------------------------ signing
# The login keychain is locked in an SSH session ("User interaction is not allowed"), so codesign gets its own
# keychain for the length of the build, and the user's keychain list is put back afterwards.
security create-keychain -p "$KCPW" "$KC" || fail keychain "could not create a keychain"
security set-keychain-settings -lut 7200 "$KC"
security unlock-keychain -p "$KCPW" "$KC"
security import "$P12" -k "$KC" -P "$(cat "$P12_PASSWORD_FILE")" -T /usr/bin/codesign -T /usr/bin/security >/dev/null \
  || fail keychain "could not import the certificate (wrong password?)"
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$KCPW" "$KC" >/dev/null
security list-keychains -d user -s "$KC" ${ORIGINAL_KEYCHAINS[@]+"${ORIGINAL_KEYCHAINS[@]}"}
echo "signing:  $(security find-identity -v -p codesigning "$KC" | tail -1 | sed 's/^ *//')"

# -------------------------------------------------------------------- build
if [ -n "${PREBUILD:-}" ]; then
  echo "prebuild: $PREBUILD"
  run bash -c "$PREBUILD" > "$OUT/prebuild.log" 2>&1 || { tail -20 "$OUT/prebuild.log"; fail prebuild "see $OUT/prebuild.log"; }
fi

PBX="${XCODEPROJ:-${WORKSPACE%.xcworkspace}.xcodeproj}/project.pbxproj"
[ -f "$PBX" ] || fail signing "project file not found: $PBX (set XCODEPROJ)"
if git ls-files --error-unmatch "$PBX" >/dev/null 2>&1; then PBX_BACKUP="$OUT/project.pbxproj.orig"; cp "$PBX" "$PBX_BACKUP"; fi
python3 "$HERE/manual_sign.py" "$PBX" "$PROFILES" || fail signing "a bundle id in PROFILES is not in the project"

if [ -n "${WORKSPACE:-}" ]; then CONTAINER=(-workspace "$WORKSPACE"); else CONTAINER=(-project "$XCODEPROJ"); fi
JOBS_FLAG=()
[ -z "${JOBS:-}" ] || JOBS_FLAG=(-jobs "$JOBS")
rm -rf "$ARCHIVE"
echo "archive -> $OUT/archive.log"
run xcodebuild "${CONTAINER[@]}" -scheme "$SCHEME" -configuration Release -destination "generic/platform=iOS" \
  -archivePath "$ARCHIVE" ${JOBS_FLAG[@]+"${JOBS_FLAG[@]}"} archive \
  DEVELOPMENT_TEAM="$TEAM_ID" OTHER_CODE_SIGN_FLAGS="--keychain $KC" > "$OUT/archive.log" 2>&1
grep -E "error:|ARCHIVE (SUCCEEDED|FAILED)" "$OUT/archive.log" | sort -u | head -20
[ -d "$ARCHIVE" ] || fail archive "see $OUT/archive.log"

GOT_VERSION=$(/usr/libexec/PlistBuddy -c "Print :ApplicationProperties:CFBundleShortVersionString" "$ARCHIVE/Info.plist")
GOT_BUILD=$(/usr/libexec/PlistBuddy -c "Print :ApplicationProperties:CFBundleVersion" "$ARCHIVE/Info.plist")
echo "archived: $GOT_VERSION ($GOT_BUILD)"
# A project generator can quietly reset the numbers (to 1.0 / 1) when Info.plist does not reference the build settings.
if [ -n "${APP_VERSION:-}" ] && { [ "$GOT_VERSION" != "$APP_VERSION" ] || [ "$GOT_BUILD" != "${APP_BUILD:-$GOT_BUILD}" ]; }; then
  fail version "expected $APP_VERSION (${APP_BUILD:-?}) but the archive is $GOT_VERSION ($GOT_BUILD)"
fi
for app in "$ARCHIVE"/Products/Applications/*.app; do
  entitlements=$(codesign -d --entitlements - "$app" 2>/dev/null)   # captured first: grep -q on a live pipe trips pipefail
  echo "$entitlements" | grep -A4 application-groups | grep -Eo 'group\.[A-Za-z0-9.-]+' | sed 's/^/app group: /'
done
if [ "$MODE" = archive ]; then echo "MAC_RELEASE_OK archive $ARCHIVE"; exit 0; fi

# ------------------------------------------------------------------- export
DESTINATION=export; [ "$MODE" = upload ] && DESTINATION=upload
{
  echo '<?xml version="1.0" encoding="UTF-8"?>'
  echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
  echo '<plist version="1.0"><dict>'
  echo "  <key>method</key><string>app-store-connect</string>"
  echo "  <key>destination</key><string>$DESTINATION</string>"
  echo "  <key>teamID</key><string>$(xml "$TEAM_ID")</string>"
  echo "  <key>signingStyle</key><string>manual</string>"
  echo "  <key>uploadSymbols</key><true/>"
  echo "  <key>provisioningProfiles</key><dict>"
  while IFS= read -r pair; do
    [ -z "$pair" ] || echo "    <key>$(xml "${pair%%=*}")</key><string>$(xml "${pair#*=}")</string>"
  done <<< "$(tr ';' '\n' <<< "$PROFILES")"
  echo "  </dict>"
  echo "</dict></plist>"
} > "$OUT/export.plist"

AUTH=()
if [ "$MODE" = upload ]; then
  AUTH=(-authenticationKeyPath "$(expand "$ASC_PRIVATE_KEY_PATH")" -authenticationKeyID "$ASC_KEY_ID" -authenticationKeyIssuerID "$ASC_ISSUER_ID")
fi
rm -rf "$OUT/export"
echo "export ($DESTINATION) -> $OUT/export.log"
# Homebrew's rsync ahead of Apple's makes exportArchive die with "Copy failed", so this one command gets a bare PATH.
run env PATH=/usr/bin:/bin:/usr/sbin:/sbin xcodebuild -exportArchive -archivePath "$ARCHIVE" -exportPath "$OUT/export" \
  -exportOptionsPlist "$OUT/export.plist" ${AUTH[@]+"${AUTH[@]}"} > "$OUT/export.log" 2>&1
RC=$?
grep -E "error|EXPORT (SUCCEEDED|FAILED)|Upload succeeded|uploaded" "$OUT/export.log" | sort -u | head -20
[ $RC -eq 0 ] || fail export "see $OUT/export.log"
if [ "$MODE" = ipa ]; then
  IPA=$(find "$OUT/export" -maxdepth 1 -name '*.ipa' | head -1)
  [ -n "$IPA" ] || fail export "no .ipa in $OUT/export"
  echo "MAC_RELEASE_OK ipa $IPA"
else
  echo "MAC_RELEASE_OK upload $GOT_VERSION ($GOT_BUILD)"
fi

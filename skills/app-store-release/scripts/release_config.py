#!/usr/bin/env python3
"""The per-app release config (.asc/release.json) and the version numbers it points at.

Run from the app's repository root.

  python release_config.py init            detect the project and write .asc/release.json (never overwrites; --force does)
  python release_config.py show            the config, the current version and build, and what is still missing
  python release_config.py bump --patch    1.2.3 -> 1.2.4 (also --minor, --major, or --version 2.0)
  python release_config.py bump --build auto      build = highest of local and App Store Connect, plus one
  python release_config.py bump --patch --build auto
  python release_config.py env             KEY=value lines for mac_release.sh
  python release_config.py profile-names   the provisioning profile names, one per line (for fetch_profiles.py)

The config holds no secrets: only ids, names and paths. Keys, certificates and passwords stay outside the repository.
Version numbers are edited where the project really keeps them:
  expo      app.json            expo.version, ios.buildNumber (android.versionCode follows if it was equal)
  xcodegen  project.yml         MARKETING_VERSION, CURRENT_PROJECT_VERSION
  xcode     *.xcodeproj         MARKETING_VERSION, CURRENT_PROJECT_VERSION in project.pbxproj
  custom    project.version_files in the config: [{"path": ..., "version": regex, "build": regex}], one group each
"""
import json
import re
import shlex
import sys
from pathlib import Path

CONFIG = Path(".asc/release.json")
SKIP = {"node_modules", "Pods", ".git", "build", "DerivedData", ".build", "vendor"}

TEMPLATE = {
    "app_id": None,
    "bundle_id": None,
    "team_id": None,
    "credentials_profile": "credentials",
    "project": {"kind": None, "workspace": None, "xcodeproj": None, "scheme": None, "prebuild": None},
    "signing": {"p12": None, "p12_password_file": None, "profiles": {}},
    "build": {
        "hosts": ["mac"],
        "mac": {"ssh": None, "dir": None, "git_remote": None},
        "github": {"repo": None, "workflow": "ios-release.yml"},
        "jobs": None,
    },
    "release": {"release_type": "AFTER_APPROVAL", "phased": False, "encryption_exempt": None,
                "whats_new": None, "review_notes": None, "with_iaps": False},
    "autonomy": None,
    "rejections": None,
}

# What the agent has to ask the user for (see references/setup.md); everything else is detected.
REQUIRED = ["app_id", "bundle_id", "team_id", "project.kind", "project.scheme", "signing.profiles", "autonomy", "rejections"]
MAC_REQUIRED = ["signing.p12", "signing.p12_password_file", "build.mac.ssh", "build.mac.dir"]


def find(pattern, depth=3):
    out = []
    for p in Path(".").glob(pattern):
        if not SKIP.intersection(p.parts) and len(p.parts) <= depth:
            out.append(p)
    return sorted(out, key=lambda p: (len(p.parts), str(p)))


def detect():
    cfg = json.loads(json.dumps(TEMPLATE))
    proj = cfg["project"]
    app_json = next((p for p in (Path("app.json"), Path("app.config.json")) if p.exists()), None)
    if app_json and '"expo"' in app_json.read_text(encoding="utf-8"):
        proj["kind"] = "expo"
        text = app_json.read_text(encoding="utf-8")
        m = re.search(r'"bundleIdentifier"\s*:\s*"([^"]+)"', text)
        cfg["bundle_id"] = m.group(1) if m else None
        proj["prebuild"] = "npm ci && npx expo prebuild --platform ios"
    elif Path("project.yml").exists():
        proj["kind"] = "xcodegen"
        proj["prebuild"] = "xcodegen generate"
        text = Path("project.yml").read_text(encoding="utf-8")
        m = re.search(r"PRODUCT_BUNDLE_IDENTIFIER:\s*\"?([\w.\-]+)", text)
        cfg["bundle_id"] = m.group(1) if m else None
        m = re.search(r"^name:\s*(\S+)", text, re.M)
        if m:
            proj["xcodeproj"], proj["scheme"] = m.group(1) + ".xcodeproj", m.group(1)
    projects = [p for p in find("**/*.xcodeproj") if "xcworkspace" not in str(p)]
    workspaces = [p for p in find("**/*.xcworkspace") if ".xcodeproj" not in str(p)]
    if projects and not proj["kind"]:
        proj["kind"] = "xcode"
    if projects and not proj["xcodeproj"]:
        proj["xcodeproj"] = projects[0].as_posix()
        proj["scheme"] = projects[0].stem
        pbx = projects[0] / "project.pbxproj"
        if pbx.exists() and not cfg["bundle_id"]:
            ids = sorted(set(re.findall(r"PRODUCT_BUNDLE_IDENTIFIER = \"?([\w.\-]+)\"?;", pbx.read_text(encoding="utf-8", errors="replace"))), key=len)
            cfg["bundle_id"] = ids[0] if ids else None
    if workspaces:
        proj["workspace"] = workspaces[0].as_posix()
    if proj["kind"] == "expo" and not proj["workspace"]:
        proj["workspace"], proj["scheme"] = "ios/<AppName>.xcworkspace", "<AppName>"  # exists only after prebuild
    for notes in ("fastlane/metadata/en-US/release_notes.txt", "AppStore/whats-new.txt", ".asc/whats-new.txt"):
        if Path(notes).exists():
            cfg["release"]["whats_new"] = notes
            break
    return cfg


def load():
    if not CONFIG.exists():
        sys.exit(f"{CONFIG} not found. Run `release_config.py init` from the app's repository root.")
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def dig(cfg, dotted):
    for part in dotted.split("."):
        cfg = (cfg or {}).get(part)
    return cfg


def missing(cfg):
    need = list(REQUIRED)
    if "mac" in (dig(cfg, "build.hosts") or []):
        need += MAC_REQUIRED
    if "github" in (dig(cfg, "build.hosts") or []):
        need.append("build.github.repo")
    return [k for k in need if not dig(cfg, k) or "<" in str(dig(cfg, k))]


# ------------------------------------------------------------------ versions
def version_files(cfg):
    kind = dig(cfg, "project.kind")
    if kind == "expo":
        path = "app.json" if Path("app.json").exists() else "app.config.json"
        return [{"path": path, "version": r'"version"\s*:\s*"([^"]+)"', "build": r'"buildNumber"\s*:\s*"([^"]+)"', "first_version_only": True}]
    if kind == "xcodegen":
        return [{"path": "project.yml", "version": r'MARKETING_VERSION:\s*"?([\w.]+)"?', "build": r'CURRENT_PROJECT_VERSION:\s*"?(\w+)"?'}]
    if kind == "xcode":
        return [{"path": str(Path(dig(cfg, "project.xcodeproj")) / "project.pbxproj"),
                 "version": r"MARKETING_VERSION = ([^;]+);", "build": r"CURRENT_PROJECT_VERSION = ([^;]+);"}]
    files = dig(cfg, "project.version_files")
    if not files:
        sys.exit('project.kind is "custom" (or unset): list the files in project.version_files, each with a "version" and a "build" regex.')
    return files


def read_versions(cfg):
    """(version, build) and a list of warnings when the files disagree."""
    versions, builds, warnings = [], [], []
    for f in version_files(cfg):
        text = Path(f["path"]).read_bytes().decode("utf-8")
        v = re.findall(f["version"], text)
        if f.get("first_version_only"):
            v = v[:1]
        versions += v
        builds += re.findall(f["build"], text)
    if not versions or not builds:
        sys.exit("could not find the version or the build number in " + ", ".join(f["path"] for f in version_files(cfg)))
    for label, values in (("version", versions), ("build", builds)):
        if len(set(values)) > 1:
            warnings.append(f"{label} is not the same everywhere: {sorted(set(values))}")
        if any("$" in x for x in values):
            sys.exit(f"the {label} is a build-setting reference ({values[0]}); point project.version_files at where the number really lives.")
    return versions[0], builds[0], warnings


def write_versions(cfg, version, build, old_build):
    for f in version_files(cfg):
        path = Path(f["path"])
        text = path.read_bytes().decode("utf-8")  # bytes in and out, so line endings stay as they were
        sub = lambda value: (lambda m: m.group(0).replace(m.group(1), value, 1))  # noqa: E731
        text, nv = re.subn(f["version"], sub(version), text, count=1 if f.get("first_version_only") else 0)
        text, nb = re.subn(f["build"], sub(build), text)
        if dig(cfg, "project.kind") == "expo":
            # Keep android.versionCode in step only where the project already kept it equal to the iOS build number.
            text = re.sub(r'("versionCode"\s*:\s*)%s\b' % re.escape(old_build), r"\g<1>" + build, text)
        path.write_bytes(text.encode("utf-8"))
        print(f"  {path}: version x{nv}, build x{nb}")


def next_version(current, part):
    nums = [int(x) for x in current.split(".")]
    i = {"major": 0, "minor": 1, "patch": 2}[part]
    while len(nums) <= i:
        nums.append(0)
    nums[i] += 1
    nums[i + 1:] = [0] * (len(nums) - i - 1)
    return ".".join(map(str, nums))


def highest_remote_build(cfg):
    sys.path.insert(0, str(Path(__file__).parent))
    from asc_api import Api
    api = Api(cfg.get("credentials_profile") if cfg.get("credentials_profile") != "credentials" else None)
    builds = api.get(f"/v1/builds?filter[app]={cfg['app_id']}&sort=-uploadedDate&limit=200&fields[builds]=version")["data"]
    return max([int(b["attributes"]["version"]) for b in builds if b["attributes"]["version"].isdigit()] or [0])


# ------------------------------------------------------------------ commands
def cmd_init(argv):
    if CONFIG.exists() and "--force" not in argv:
        sys.exit(f"{CONFIG} already exists. Edit it, or pass --force to start over.")
    cfg = detect()
    CONFIG.parent.mkdir(exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {CONFIG} (project kind: {cfg['project']['kind'] or 'not detected'}, bundle id: {cfg['bundle_id'] or 'not detected'}).")
    print("Still to fill in: " + ", ".join(missing(cfg)))


def cmd_show(_):
    cfg = load()
    print(json.dumps(cfg, indent=2))
    version, build, warnings = read_versions(cfg)
    print(f"\nversion {version}  build {build}")
    for w in warnings:
        print("WARNING:", w)
    gaps = missing(cfg)
    print("Missing: " + ", ".join(gaps) if gaps else "Config is complete.")
    sys.exit(2 if gaps else 0)


def cmd_bump(argv):
    cfg = load()
    version, build, warnings = read_versions(cfg)
    for w in warnings:
        print("WARNING:", w)
    new_version, new_build = version, build
    for part in ("major", "minor", "patch"):
        if f"--{part}" in argv:
            new_version = next_version(version, part)
    if "--version" in argv:
        new_version = argv[argv.index("--version") + 1]
    if "--build" in argv:
        value = argv[argv.index("--build") + 1]
        if value == "auto":
            if not cfg.get("app_id"):
                sys.exit("--build auto needs app_id in the config.")
            value = str(max(int(build), highest_remote_build(cfg)) + 1)
        new_build = value
    if (new_version, new_build) == (version, build):
        sys.exit("nothing to change: pass --patch, --minor, --major, --version X or --build N|auto")
    print(f"version {version} -> {new_version}, build {build} -> {new_build}")
    write_versions(cfg, new_version, new_build, build)


def cmd_env(_):
    cfg = load()
    version, build, _ = read_versions(cfg)
    profiles = ";".join(f"{b}={n}" for b, n in (dig(cfg, "signing.profiles") or {}).items())
    values = {
        "APP_VERSION": version, "APP_BUILD": build, "TEAM_ID": cfg.get("team_id"), "BUNDLE_ID": cfg.get("bundle_id"),
        "PROJECT_DIR": dig(cfg, "build.mac.dir"), "WORKSPACE": dig(cfg, "project.workspace"), "XCODEPROJ": dig(cfg, "project.xcodeproj"),
        "SCHEME": dig(cfg, "project.scheme"), "PREBUILD": dig(cfg, "project.prebuild"), "PROFILES": profiles,
        "P12": dig(cfg, "signing.p12"), "P12_PASSWORD_FILE": dig(cfg, "signing.p12_password_file"), "JOBS": dig(cfg, "build.jobs"),
    }
    for k, v in values.items():
        if v not in (None, ""):
            print(f"{k}={shlex.quote(str(v))}")


def cmd_profile_names(_):
    for name in (dig(load(), "signing.profiles") or {}).values():
        print(name)


if __name__ == "__main__":
    commands = {"init": cmd_init, "show": cmd_show, "bump": cmd_bump, "env": cmd_env, "profile-names": cmd_profile_names}
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")  # no CR on Windows: `env` output is pasted into a shell
    commands[sys.argv[1]](sys.argv[2:])

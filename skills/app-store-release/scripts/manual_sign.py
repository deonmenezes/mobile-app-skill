#!/usr/bin/env python3
"""Switch the Release configuration of each app target to manual App Store signing, one profile per bundle id.

  python3 manual_sign.py App.xcodeproj/project.pbxproj "com.example.app=Example AppStore;com.example.app.widget=Example Widget AppStore"
  python3 manual_sign.py App.xcodeproj/project.pbxproj "..." --check     report only, change nothing

Why: automatic signing needs an unlocked login keychain and a development certificate, which an SSH session or a CI
runner does not have. Setting the profile on the xcodebuild command line instead would apply it to every target,
including extensions and packages, and break the build. Only stdlib, so it runs with the python3 that ships with Xcode.

Exit codes: 0 every mapped bundle id was found, 2 one was not (wrong id, or the id is built from a variable).
"""
import re
import sys
from pathlib import Path

BLOCK = re.compile(r"\w+ (?:/\* [^*]+ \*/ )?= \{\s*isa = XCBuildConfiguration;.*?\n\t\t\};", re.S)
SIGNING = re.compile(r"\n\s*(?:CODE_SIGN_STYLE|PROVISIONING_PROFILE_SPECIFIER|PROVISIONING_PROFILE|\"?CODE_SIGN_IDENTITY(?:\[sdk=[^\]]*\])?\"?) = [^;]*;")


def main(argv):
    check = "--check" in argv
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    path = Path(args[0])
    profiles = dict(pair.split("=", 1) for pair in args[1].split(";") if "=" in pair)
    text = path.read_bytes().decode("utf-8")
    seen, unmapped = set(), set()

    def fix(m):
        block = m.group(0)
        if "name = Release;" not in block:
            return block
        bid = re.search(r"PRODUCT_BUNDLE_IDENTIFIER = \"?([^\";]+)\"?;", block)
        if not bid:
            return block  # a project-level configuration, not a target's
        if bid.group(1) not in profiles:
            unmapped.add(bid.group(1))
            return block
        seen.add(bid.group(1))
        indent = re.search(r"buildSettings = \{\n(\s*)", block)
        pad = indent.group(1) if indent else "\t\t\t\t"
        block = SIGNING.sub("", block)
        # "iPhone Distribution" matches both the older "iPhone Distribution" and the newer "Apple Distribution" certificates.
        settings = (f'buildSettings = {{\n{pad}CODE_SIGN_STYLE = Manual;\n{pad}CODE_SIGN_IDENTITY = "iPhone Distribution";'
                    f'\n{pad}PROVISIONING_PROFILE_SPECIFIER = "{profiles[bid.group(1)]}";')
        return block.replace("buildSettings = {", settings, 1)

    new = BLOCK.sub(fix, text)
    for b in sorted(seen):
        print(f"manual signing: {b} -> {profiles[b]}")
    # Test targets and the like are fine to leave; an app extension here would fail the archive.
    for b in sorted(unmapped):
        print(f"left alone (no profile mapped): {b}")
    missing = sorted(set(profiles) - seen)
    for b in missing:
        print(f"NOT FOUND in a Release configuration: {b}")
    if not check and new != text:
        path.write_bytes(new.encode("utf-8"))
    sys.exit(2 if missing else 0)


if __name__ == "__main__":
    main(sys.argv[1:])

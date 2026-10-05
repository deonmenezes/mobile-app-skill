# Skill map

Every skill in this pack, grouped by the stage where `mobile-app` uses it. Vendored skills are unmodified copies; creators, licences and pinned commits are in `CREDITS.md` at the repository root.

## Orchestration (Deon Menezes, MIT)

| Skill | Use it for |
|---|---|
| `mobile-app` | The whole path: intake, stack, build, check, ship, watch review |
| `expedite-review` | Deciding whether an Apple expedite request is justified and drafting it |

## Build: Expo and React Native

| Skill | Use it for | Upstream |
|---|---|---|
| `expo-overview` | Entry point and router for any Expo or EAS task. Load it first | expo/skills |
| `expo-project-structure` | Folder layout for a new Expo Router project | expo/skills |
| `expo-router` | File-based routes, tabs, stacks, modals, headers | expo/skills |
| `expo-native-ui` | Native-feeling screens, styling, controls, media | expo/skills |
| `expo-ui` | `@expo/ui` components: sheets, pickers, sliders, menus | expo/skills |
| `expo-data-fetching` | Network requests, caching, offline, loaders | expo/skills |
| `expo-dev-client` | Development builds | expo/skills |
| `expo-upgrade` | Expo SDK upgrades and dependency fixes | expo/skills |
| `react-native-best-practices` | Performance: FPS, startup, bundle size, memory | callstackincubator/agent-skills |
| `react-navigation` | React Navigation stacks, tabs, drawers | callstackincubator/agent-skills |
| `upgrading-react-native` | React Native version upgrades | callstackincubator/agent-skills |

## Build: Swift and SwiftUI

| Skill | Use it for | Upstream |
|---|---|---|
| `swiftui-expert-skill` | Writing, reviewing and refactoring SwiftUI | AvdLee/SwiftUI-Agent-Skill |
| `swiftui-ui-patterns` | View and component patterns, navigation, tabs | Dimillian/Skills |
| `swiftui-liquid-glass` | The iOS 26+ Liquid Glass API | Dimillian/Skills |
| `swift-concurrency-expert` | Swift 6.2+ concurrency review and fixes | Dimillian/Skills |
| `swiftui-pro` | A full SwiftUI code review | twostraws/SwiftUI-Agent-Skill |

## Build: Android (Kotlin, Jetpack Compose)

| Skill | Use it for | Upstream |
|---|---|---|
| `navigation-3` | Jetpack Navigation 3 | android/skills |
| `edge-to-edge` | Edge-to-edge and insets in Compose | android/skills |
| `testing-setup` | A testing strategy and setup | android/skills |
| `migrate-xml-views-to-jetpack-compose` | Moving XML views to Compose | android/skills |
| `r8-analyzer` | R8 keep rules and shrinking | android/skills |

## Check: before submission

| Skill | Use it for | Upstream |
|---|---|---|
| `asc-submission-health` | `asc validate`, `asc review doctor`, blocker diagnosis, review monitoring | rorkai/app-store-connect-cli-skills |
| `asc-metadata-sync` | App Store metadata sync and character-limit validation | rorkai/app-store-connect-cli-skills |
| `asc-screenshot-resize` | App Store screenshot sizes (uses macOS `sips`) | rorkai/app-store-connect-cli-skills |
| `gplay-preflight` | Offline scan of an AAB or APK with nine scanners | tamtom/gplay-cli-skills |
| `gplay-submission-checks` | `gplay validate`, listing, data safety, common rejection fixes | tamtom/gplay-cli-skills |
| `play-policy-insights` | Google's policy audit: data safety, demo credentials, restricted permissions | android/skills |
| `play-billing-library-version-upgrade` | Play Billing Library upgrades | android/skills |

## Ship: iOS

| Skill | Use it for | Upstream |
|---|---|---|
| `asc-cli-usage` | Correct `asc` commands, flags, output and auth | rorkai/app-store-connect-cli-skills |
| `asc-id-resolver` | App, build, version and group IDs from names | rorkai/app-store-connect-cli-skills |
| `asc-app-create-ui` | Creating the App Store Connect app record through the browser | rorkai/app-store-connect-cli-skills |
| `asc-signing-setup` | Bundle IDs, certificates, provisioning profiles | rorkai/app-store-connect-cli-skills |
| `asc-xcode-build` | Archive, export an IPA, version and build numbers (Mac) | rorkai/app-store-connect-cli-skills |
| `asc-build-lifecycle` | Build processing, latest build, cleanup | rorkai/app-store-connect-cli-skills |
| `asc-testflight-orchestration` | TestFlight groups, testers, distribution | rorkai/app-store-connect-cli-skills |
| `asc-shots-pipeline` | Simulator screenshot capture, framing, upload (Mac) | rorkai/app-store-connect-cli-skills |
| `asc-whats-new-writer` | Localised What's New text | rorkai/app-store-connect-cli-skills |
| `asc-release-flow` | Stage, upload, publish and submit a release with dry-run | rorkai/app-store-connect-cli-skills |
| `rork-local` | Browser simulator preview and publishing UI (Mac) | rorkai/rork-local |
| `app-store-changelog` | Release notes from git history | Dimillian/Skills |

## Ship: Android

| Skill | Use it for | Upstream |
|---|---|---|
| `gplay-cli-usage` | Correct `gplay` commands, flags, output and auth | tamtom/gplay-cli-skills |
| `gplay-gradle-build` | Building and signing an AAB with Gradle | tamtom/gplay-cli-skills |
| `gplay-release-flow` | `gplay release`, `gplay promote`, tracks | tamtom/gplay-cli-skills |
| `gplay-testers-orchestration` | Internal and closed-test testers, promotion between tracks | tamtom/gplay-cli-skills |
| `gplay-rollout-management` | Staged rollout: update, halt, resume, complete | tamtom/gplay-cli-skills |
| `gplay-metadata-sync` | Play listing text and localisation | tamtom/gplay-cli-skills |
| `gplay-screenshot-automation` | Play listing screenshots and graphics | tamtom/gplay-cli-skills |

## Ship: both stores, Expo projects

| Skill | Use it for | Upstream |
|---|---|---|
| `eas-app-stores` | EAS cloud builds and store submission (EAS costs apply) | expo/skills |

## Not bundled, worth knowing

These are linked, not copied, because they have no licence file or are hosted products. See `CREDITS.md`.

- Software Mansion's skills (animations, gestures): https://github.com/software-mansion-labs/skills
- Vercel's `react-native-skills`: https://github.com/vercel-labs/agent-skills
- Axiom, a large Apple-platform skill set by Charles Wiltgen: https://github.com/CharlesWiltgen/Axiom
- The rest of each upstream pack: Expo has 24 skills, the `asc` pack 25, the `gplay` pack 17, `android/skills` 25. Install commands are in `CREDITS.md`.

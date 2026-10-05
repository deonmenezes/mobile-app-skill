# What this cannot do

Read this before promising the user anything. Every quote below was taken from the page linked beside it on 2026-10-05.

## It cannot guarantee approval

Pre-submission checks exist for both stores, and this skill runs them. They lower the risk. They do not remove it.

- `asc validate` and `asc review doctor` check that a submission is complete: build attached, required metadata and screenshots, privacy policy URL, age rating, categories, pricing and availability, App Review contact information and demo credentials, and leftover placeholder text such as `Lorem ipsum`, `TODO`, `TBD` and `FIXME`. They do not judge how the app behaves. The `asc` README says its placeholder lint "intentionally does not judge platform names, roadmap language, or beta/demo wording".
- `gplay preflight` scans the build file offline with nine scanners (manifest, permissions, native libraries, metadata, secrets, billing, privacy, policy, size). The `gplay-preflight` skill itself warns that a missing finding is not proof of compliance when a build is heavily obfuscated.
- Google's `play-policy-insights` skill audits three policy domains only: "data safety, demo login credentials, and restricted permissions".
- Rork's hosted AI App Store Reviewer (not part of this pack) states the same limit about itself: "The reviewer is advisory. It never blocks a submission and it never promises an approval. Apple makes the final decision, and Apple's own review still takes days." (https://docs.rork.com/ai-app-store-reviewer)
- Rork's review guide: "Rejections are common and expected, especially on first submissions." (https://docs.rork.com/appstore-submission-checklist/app-review-guide)

## It cannot make review faster

- Apple: "On average, 90% of submissions are reviewed in less than 24 hours." (https://developer.apple.com/distribute/app-review/) That is an average across all submissions.
- Apple: "If your submission is incomplete, review times may be delayed or your submission may not pass." (same page)
- Google: "Certain apps may be subject to extended reviews, which may result in review times of up to 7 days or longer in exceptional cases." (https://support.google.com/googleplay/android-developer/answer/9859751)
- Expedited review is a request the developer files with Apple by hand. No CLI or skill in this pack can file it. The `expedite-review` skill only checks whether the situation fits Apple's stated criteria and drafts the text. Apple decides. Google publishes no expedite process on the pages checked.

## It cannot skip Google's testing requirement

Google: "Developers with personal accounts created after November 13, 2023, must run a closed test for their app with a minimum of 12 testers who have been opted in continuously for at least 14 days." (https://support.google.com/googleplay/android-developer/answer/14151465)

A new personal account therefore cannot reach production on Google Play in a day, whatever tool is used.

## It cannot do the first Play Console steps

The `gplay` README: "Initial public-app setup, first upload, ordinary Google-managed Play App Signing enrollment, and legal declarations still require a manual Play Console handoff." (https://github.com/tamtom/play-console-cli)

Expo's bundled `eas-app-stores` skill says the same about creating the app: "The app must exist in Play Console before EAS can submit. Create it manually first."

## It cannot build an iOS binary on Windows or Linux by itself

Building an `.ipa` needs macOS with Xcode, or a cloud build such as EAS. The `asc` binary itself runs on Windows, so validation, submission and status checks work there once a build has been uploaded. `asc-xcode-build`, `asc-shots-pipeline`, `asc-screenshot-resize` and `rork-local` need a Mac.

`rork-local`'s own skill tells you to start it with `npx rork-local`. On 2026-10-05 the npm registry returned 404 for that package name. If that is still the case, run it from a checkout of https://github.com/rorkai/rork-local with the commands in its README: `bun install`, `bun run build`, `bun start`.

## It cannot create your accounts or pay your fees

Apple Developer Program: $99 a year. Google Play Console: $25 once. Both stores verify who you are. (Fees and verification as stated at https://docs.rork.com/introduction/deploy-your-app)

## Manual review pass

Do this with the user before any submission. The automated checks do not cover it.

1. **Completeness.** Apple: "On average, over 40% of unresolved issues are related to guideline 2.1: App Completeness, which covers crashes, placeholder content, incomplete information, and more." Open every screen on a real device or simulator. No crash on the main flow, no placeholder text or images, no button that does nothing.
2. **Reviewer access.** If the app has a login, the reviewer needs working demo credentials. Both `asc validate` and `play-policy-insights` look for them; confirm the account actually works.
3. **Privacy.** A reachable privacy policy URL, App Privacy answers in App Store Connect, and the Data safety form in Play Console all have to match what the app really collects.
4. **Payments.** If the app sells digital goods, run `asc validate iap` / `asc validate subscriptions` on iOS and read the `billing` findings from `gplay preflight` on Android.
5. **The rules themselves.** Read the sections that apply to the app's category. These are the source of truth, and no skill here replaces them:
   - Apple App Review Guidelines: https://developer.apple.com/app-store/review/guidelines/
   - Google Play Developer Policy Center: https://play.google.com/about/developer-content-policy/

If a step turns something up, fix it and re-run Stage 4 before submitting.

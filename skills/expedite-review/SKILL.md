---
name: expedite-review
description: Check whether an App Store submission meets Apple's stated criteria for an expedited review, draft the request text (critical bug or time-bound event), and give the link to Apple's request form. Use when the user says "expedite my review", "speed up App Store review", "urgent fix needs to go live", "my launch event is in a few days and the app is still in review", or asks whether Google Play reviews can be expedited. This skill prepares the request. It cannot file it and cannot make a review faster.
license: MIT
---

# Expedite review

This skill does three things: decides whether a request is justified, drafts it, and tells the user where to file it. The user files it. Apple decides.

## What is true about expedited reviews

- Apple: "You can request the review of your app to be expedited if you face extenuating circumstances, such as fixing a critical bug in your app or releasing your app to coincide with an event you're directly associated with." (https://developer.apple.com/distribute/app-review/)
- The request is a form on Apple's site, behind Apple sign-in: https://developer.apple.com/contact/app-store/?topic=expedite
- Expedites are granted at Apple's discretion. Rork's review guide says the same: "Expedited reviews are **not guaranteed**, but they are often approved if the reason is valid." (https://docs.rork.com/appstore-submission-checklist/app-review-guide)
- No CLI or skill can file the request. `asc` has no expedite command.
- **Google Play has no published expedite process.** Google's own help says some reviews take "up to 7 days or longer in exceptional cases" (https://support.google.com/googleplay/android-developer/answer/9859751). See "Google Play" below for what can be done instead.

Never tell the user a request will be granted, and never tell them how long it will take.

## Step 1: Does the situation fit?

Apple names two cases. Its wording is "such as", so they are examples, but they are the only ones Apple spells out. Ask the user which applies.

| Case | Fits when | Does not fit when |
|---|---|---|
| Critical bug | The version live on the App Store has a serious bug, a fixed build exists, and the bug can be reproduced step by step on the live version | The bug is cosmetic, or cannot be reproduced, or the "fix" is really a new feature |
| Event | The release is tied to a real event with a fixed date, and the developer is directly associated with that event | The date is a self-chosen launch day with no event behind it |

If neither applies, say so plainly: wanting to be live sooner is not something Apple lists. The user may still file a request, and the text should describe the real circumstances. Do not dress it up.

## Step 2: Is the submission ready to be expedited?

Apple's wording assumes there is a submission to speed up (a bug fix being submitted, or an app "still in review"), so get that in order first.

1. Check where the submission stands:

```bash
asc review status --app "APP_ID" --version "1.2.3" --platform IOS --output table
```

2. If the fix has not been submitted yet, submit it first with the `asc-release-flow` skill, after `asc validate` passes:

```bash
asc validate --app "APP_ID" --version "1.2.3" --platform IOS --output table
```

3. Fix anything incomplete before asking for speed. Apple: "If your submission is incomplete, review times may be delayed or your submission may not pass."

## Step 3: Draft the request

Write it in the user's voice, short and factual. Fill every bracket with real details from the user; if a detail is missing, ask for it. Do not invent impact numbers.

### Critical bug

Apple: "When submitting an expedited review to fix a critical bug, include the steps to reproduce the bug on the current version of your app."

```text
App: [App name] ([Apple ID / bundle ID])
Version in review: [new version] (build [build number])
Version currently on the App Store: [live version]

Reason: critical bug fix.

What is broken on the live version:
[One or two sentences. What the user sees, and who is affected.]

Steps to reproduce on version [live version]:
1. [Step]
2. [Step]
3. [Step]
Result: [what happens]
Expected: [what should happen]

What the submitted version changes:
[One sentence. The fix only.]

Contact: [name, email, phone]
```

### Event

Apple: "Make sure your request includes the event, date of the event, and your app's association with the event."

```text
App: [App name] ([Apple ID / bundle ID])
Version in review: [version] (build [build number])
Submitted on: [date]

Reason: release tied to an event.

Event: [name of the event]
Date of the event: [date]
Our association with the event: [organiser / official partner / exhibitor / etc., in one or two sentences, with a link if one exists]

Why this version is needed for the event:
[One or two sentences.]

Contact: [name, email, phone]
```

Apple describes the event case this way: "if your app is still in review and the launch of your event is quickly approaching, you can request to have your app review expedited." Its first advice for event apps is different, so pass it on for next time: "For apps associated with an event, we recommend you plan and schedule the release of your app in App Store Connect."

## Step 4: File it

Give the user the link and the drafted text. They sign in and submit it themselves.

https://developer.apple.com/contact/app-store/?topic=expedite

## Step 5: After filing

- Watch the submission. The command exits 0 when approved, 1 when rejected, 7 when still pending at the timeout:

```bash
asc status --app "APP_ID" --until review-done --timeout 2h --output json
```

- Do not cancel and resubmit to "restart" the review.
- If the request is declined, the normal review continues. Apple says that on average 90% of submissions are reviewed in less than 24 hours.

## Google Play

There is no expedite request to draft. What can be done:

- If a bad release is rolling out, stop it reaching more users while the fix is reviewed:

```bash
gplay rollout halt --package com.example.app --track production
```

- Submit the fix normally with the `gplay-release-flow` skill and run `gplay preflight` first, so it is not delayed by something avoidable.
- Tell the user the honest expectation: Google publishes no typical review time, and says extended reviews can take up to 7 days or longer.

## Report to the user

State which case applies (or that none does), the current review state you verified, the drafted text, the form link, and one sentence making clear that Apple decides and nothing here guarantees a faster review.

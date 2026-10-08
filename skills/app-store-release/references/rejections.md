# When App Review says no

## What the API tells you, and what it does not

The API reports only that something is wrong:

- a review submission in state `UNRESOLVED_ISSUES`
- a version in `REJECTED`, `METADATA_REJECTED` or `INVALID_BINARY`

`asc_status.py` prints both and exits 1. The reviewer's actual message, the guideline number, the screenshots they attach and the reply box live only in the **Resolution Center** on the web. There is no public API for it, and an API key cannot open the private one. Apple's notification email says a submission needs attention and often names the guideline, but usually leaves out the detail.

So the first step depends on `rejections` in the config:

| Setting | Do |
|---|---|
| `browser` | In a browser where the user is signed in to App Store Connect, open the app, then the "App Review" section in the sidebar, then the submission with the unresolved issue. Read the whole thread, including attachments. If a sign-in or a two-factor prompt appears, stop and ask the user to complete it. Never type their Apple ID password. |
| `paste` | Tell the user the version was rejected and ask them to paste the message from the Resolution Center. Wait. |
| `email` | Find Apple's mail about the submission. If it does not contain the reviewer's wording, fall back to asking the user. |

Write the message down in the conversation, verbatim, before doing anything else. Everything after depends on reading it exactly.

## Which kind is it

| The message is | It needs |
|---|---|
| A question ("Does your app support...?", "Where can we find...?", "Information Needed", often guideline 2.1) | **An answer, not a new build.** Nothing is wrong with the app yet. |
| About the listing: screenshots, description, name, a purchase's metadata, a broken privacy link | **New metadata.** No new build. The state is usually `METADATA_REJECTED`. |
| About behaviour: a crash, a bug, a missing feature, a broken login, a purchase that does not work, a guideline the app breaks | **A new build**, and usually new review notes. |
| A policy objection to what the app is or does | A decision for the user. Do not rebuild until they have chosen: change the app, argue the case in a reply, or appeal. |

Do not resubmit the same build with the same notes and hope for a different reviewer. Say so if the user asks for it.

## Order of operations

The order matters because cancelling a submission deletes the reply box on its thread.

1. **Reply in the thread first**, if there is anything to say: the answer to a question, or one line saying a fix is coming in build N. The user sends it, or the agent does in the signed-in browser after showing the user the text.
2. **Put the same answer in the App Review notes** (`asc_submit.py --notes FILE`, 4000 characters at most). The next reviewer may not read the old thread. A good note for a question is three lines: the answer, where in the app to see it, and the steps to get there.
3. **Fix what needs fixing**: metadata through App Store Connect or its API; code through a normal build with a new build number and the same version number.
4. **Resubmit:**
   - Metadata or answer only: in the Resolution Center thread, resubmit the same version. Or run `asc_submit.py` for the same version and build; the rejected version is editable again and the script reuses it.
   - New build: `release_config.py bump --build auto`, build, upload, then `asc_submit.py --app ... --version SAME --build NEW`.
5. If a submission is stuck in `UNRESOLVED_ISSUES` and blocks the new one, `asc_submit.py --replace-in-review` cancels it. Do step 1 before this.

After cancelling, App Store Connect can answer 500 to new submission items for several minutes. `asc_submit.py` retries every 3 minutes; let it run.

## In-app purchases after a rejection or a cancel

Purchases that were in the cancelled submission fall back to `READY_TO_SUBMIT`. They have to be added to the new submission again (`--with-iaps`, or "Add for Review" on the web for first-time subscriptions). A version that goes back to review without the purchases it sells is rejected for that alone.

## Things that are not rejections

- **`INVALID_BINARY`**: the build failed Apple's automated checks after submission. The reason is in an email to the uploader. Fix, bump the build number, upload again.
- **A build that never appears after upload**: processing failed. Same email. Common causes are a missing usage-description string for a permission, an entitlement the profile lacks, or a build number that already exists.
- **Stuck in "Waiting for Review" for days**: not a rejection, and cancelling and resubmitting puts the app at the back of the queue. Wait, or, for a real emergency, use the pack's `expedite-review` skill.

## Report to the user

State the guideline and the reviewer's wording, which of the four kinds it is, what was changed, what was replied, and the new state verified with `asc_status.py`. If the next step is a decision only they can make, say which one and stop.

# First release of a new app

An update reuses almost everything from the version before it. A first release has nothing to reuse, and several of the missing pieces are not reported by any check until Apple rejects the submission or, worse, approves an app nobody can download. Work through this list before the first `asc_submit.py --submit`.

Items marked **web** cannot be done through the API. Do them in App Store Connect in a browser the user is signed in to, or hand them to the user.

## Account

1. **Membership and agreements are current.** An expired Apple Developer Program membership or an unaccepted agreement makes the API answer 403 on everything, or 409 on submission only. Only the Account Holder can fix either: developer.apple.com/account, then App Store Connect > Business. **web**
2. **Paid apps or in-app purchases need the Paid Applications agreement**, with tax and banking filled in. Without it, purchases never leave "Missing Metadata". **web**
3. **EU availability needs the Digital Services Act trader declaration.** Until it is filed and approved, the 27 EU territories stay off sale for every app on the account (`TRADER_STATUS_NOT_PROVIDED`). App Store Connect > Business > Compliance. Closing the dialog before the final step discards everything entered, verification included. **web**

## The app record

4. **Register the bundle id** for the app and for each extension (`POST /v1/bundleIds`, or the developer portal).
5. **Create the app record.** There is no public API for it. Name, primary language, bundle id, SKU. **web** (The pack's `asc-app-create-ui` skill automates the form.) Store names are unique: have two fallbacks ready.
6. **Capabilities and App Groups.** Enabling a capability through the API works, but an App Group cannot be created or assigned that way: create the group and assign it under each App ID in the developer portal, then **regenerate the provisioning profiles**. A profile made before the change does not carry the group, and the app is signed without it. **web**

## Signing

7. One Apple Distribution certificate as a `.p12` on the build host, and one App Store provisioning profile per signed bundle id. Check them with `fetch_profiles.py`, which prints the App Groups each profile carries.
8. If the build adds an entitlement the profile lacks (push notifications from a library is the common one), the archive fails at signing. Remove the entitlement or add the capability and regenerate the profile.

## The listing

9. **Name (30), subtitle (30), promotional text (170), description (4000), keywords (100), What's New (4000), review notes (4000).** The limits are hard; check lengths before uploading text.
10. **Screenshots** for the largest iPhone size at least. iPad screenshots are required if the app runs on iPad. They process asynchronously after upload and a submission fails while any is still processing. A script that re-uploads them can leave duplicates, so replace, do not append.
11. **Categories, age rating, copyright, support URL, privacy policy URL.** The privacy policy has to be a reachable page.
12. **App Privacy answers** ("Data Not Collected" or the real list), published. **web**
13. **Price.** Free is a price and still has to be set.
14. **Availability.** This is a separate step from price, and the easiest one to miss: an app with a price and no availability record passes review, shows `READY_FOR_SALE`, and is on sale nowhere. Check and fix it with:

    ```bash
    python scripts/asc_availability.py APP_ID          # report
    python scripts/asc_availability.py APP_ID --apply  # all territories, only if there is no record
    ```

## Review details

15. **Contact name, phone and email** for App Review, and a **demo account** if the app has a login. The account has to work on the day of review.
16. **Review notes** that tell the reviewer what they cannot guess: how to reach the paid features, which hardware a feature needs and how to see it without that hardware, why each permission is asked for, anything that looks like a policy problem but is not.
17. **Export compliance.** Set `ITSAppUsesNonExemptEncryption` in Info.plist so no build waits on the question.

## In-app purchases and subscriptions

18. Each needs a reference name, product id, price, at least one localisation, and a review screenshot before it reaches `READY_TO_SUBMIT`.
19. **First-time purchases are reviewed with an app version, in the same submission.** `asc_submit.py --with-iaps` adds them. For an app's first subscriptions the API may refuse; then add the subscription group to the version's draft submission with "Add for Review" on the group's page. **web**
20. The review notes for each purchase and the app's own notes must agree with what the app does (trial length, free limits). A mismatch is a rejection.

## The build

21. **Run the real thing first.** Upload to TestFlight and install it on a real phone. Create an internal TestFlight group that gets every build (`POST /v1/betaGroups` with `isInternalGroup` and `hasAccessToAllBuilds`); adding people to an internal group may have to be done on the web.
22. **Walk every screen.** No placeholder text, no dead buttons, no crash on the main path. Apple attributes a large share of rejections to incomplete apps.
23. **iPad.** If the app is iPhone-only it can still be reviewed on an iPad in compatibility mode. Make sure it launches and is usable there.
24. If the app has a widget, a watch app or another extension, say in the review notes how to add and see it. If it has none and the listing suggests one, expect to be asked.

## Submitting

25. A new app has **one** editable version until its first release. To change the number before then, the version is renamed, not replaced. `asc_submit.py` does this by itself.
26. Dry-run `asc_submit.py`, fix every blocker, then `--submit`.
27. After approval, run `asc_availability.py` and open the store page. Do not report "live" from the version state alone.

A first submission is more likely to be rejected than an update. That is normal, and the next round is usually a reply or a small fix: see rejections.md.

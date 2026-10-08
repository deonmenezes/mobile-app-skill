#!/usr/bin/env python3
"""Check where an app is on sale, and create the availability record when there is none.

  python asc_availability.py APP_ID            report (read-only)
  python asc_availability.py APP_ID --apply    if the app has NO availability record, offer it in every territory

Why this exists: price and availability are separate steps in App Store Connect. An app with a price but no
availability record passes review, shows READY_FOR_SALE, and is on sale in no country. Nothing warns about it.

--apply only ever creates a missing record. It never changes an existing one: to narrow the list of countries,
use App Store Connect > Pricing and Availability.
Exit codes: 0 on sale somewhere or record created, 2 no availability record (report mode), 4 API error.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from asc_api import Api, ApiError  # noqa: E402


def main(argv):
    profile = None
    if "--profile" in argv:
        i = argv.index("--profile")
        profile = argv[i + 1]
        del argv[i:i + 2]
    apps = [a for a in argv if a.isdigit()]
    if not apps:
        sys.exit(__doc__)
    app = apps[0]
    sys.stdout.reconfigure(encoding="utf-8")
    api = Api(profile)
    try:
        api.get(f"/v1/apps/{app}/appAvailabilityV2")
    except ApiError as e:
        if e.status != 404:
            raise
        print("No availability record: this app is offered in no country.")
        if "--apply" not in argv:
            print("Run again with --apply to offer it in every territory.")
            sys.exit(2)
        territories = [t["id"] for t in api.get_all("/v1/territories?limit=200")]
        # The ids are local placeholders and the API wants them written literally as ${USA}, braces included.
        local = ["${" + t + "}" for t in territories]
        api.post("/v2/appAvailabilities", {
            "data": {"type": "appAvailabilities", "attributes": {"availableInNewTerritories": True},
                     "relationships": {"app": {"data": {"type": "apps", "id": app}},
                                       "territoryAvailabilities": {"data": [{"type": "territoryAvailabilities", "id": i} for i in local]}}},
            "included": [{"type": "territoryAvailabilities", "id": i, "attributes": {"available": True},
                          "relationships": {"territory": {"data": {"type": "territories", "id": t}}}}
                         for i, t in zip(local, territories)]})
        print(f"Created: available in {len(territories)} territories. They take a while to move from processing to available.")

    states = {}
    for t in api.get_all(f"/v2/appAvailabilities/{app}/territoryAvailabilities?limit=200&fields[territoryAvailabilities]=available,contentStatuses"):
        for s in t["attributes"].get("contentStatuses") or ["UNKNOWN"]:
            states[s] = states.get(s, 0) + 1
    for s, n in sorted(states.items(), key=lambda x: -x[1]):
        print(f"  {n:>4}  {s}")
    if states.get("TRADER_STATUS_NOT_PROVIDED"):
        print("The EU territories stay off sale until the Digital Services Act trader status is declared for the account:\n"
              "App Store Connect > Business > Compliance. It is web-only and applies to every app on the team.")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except ApiError as e:
        print(e.describe())
        sys.exit(4)

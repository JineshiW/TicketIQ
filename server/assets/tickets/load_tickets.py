import json
import requests
import time


# ============================================================
# LOAD GITHUB TICKETS
# ============================================================

TICKET_FILE = "github_tickets.json"

with open(TICKET_FILE, "r") as f:
    tickets = json.load(f)


print(f"Loaded {len(tickets)} tickets from {TICKET_FILE}")


# ============================================================
# API CONFIGURATION
# ============================================================

URL = "http://127.0.0.1:8000/tickets/batch"

BATCH_SIZE = 20


# ============================================================
# IMPORT
# ============================================================

total_added = 0
total_skipped = 0


for i in range(0, len(tickets), BATCH_SIZE):

    batch = tickets[
        i:i + BATCH_SIZE
    ]

    batch_number = (
        i // BATCH_SIZE
    ) + 1

    print(
        f"\nSending batch {batch_number} "
        f"({len(batch)} tickets)..."
    )

    try:

        response = requests.post(
            URL,
            json=batch,
            timeout=120,
        )

    except requests.RequestException as exc:

        print(
            f"Batch {batch_number} failed with request error:"
        )

        print(exc)

        continue


    # ========================================================
    # SUCCESS
    # ========================================================

    if response.status_code == 200:

        try:
            result = response.json()

        except ValueError:

            print(
                f"Batch {batch_number} returned "
                f"invalid JSON:"
            )

            print(response.text)

            continue


        added = result.get(
            "added",
            0,
        )

        skipped = result.get(
            "skipped",
            [],
        )


        total_added += added
        total_skipped += len(skipped)


        print(
            f"Batch {batch_number}: "
            f"added={added}, "
            f"skipped={len(skipped)}"
        )


    # ========================================================
    # SERVER ERROR
    # ========================================================

    else:

        print(
            f"Batch {batch_number} FAILED"
        )

        print(
            f"HTTP {response.status_code}"
        )

        print(
            response.text
        )


    time.sleep(0.2)


# ============================================================
# FINAL RESULT
# ============================================================

print("\n========================================")
print("IMPORT COMPLETE")
print("========================================")

print(
    f"Tickets loaded from JSON: {len(tickets)}"
)

print(
    f"Total added: {total_added}"
)

print(
    f"Total skipped: {total_skipped}"
)

print("========================================")
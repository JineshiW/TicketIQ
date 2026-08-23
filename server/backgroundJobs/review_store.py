import json
import os
import logging
import threading
from datetime import datetime, timezone
from typing import Optional


logger = logging.getLogger("TicketIQ")


_STORE_LOCK = threading.RLock()


_STORE_PATH = os.path.join(
    os.path.dirname(__file__),
    "cluster_reviews.json",
)


# ============================================================
# STORE IO
# ============================================================

def _load_store() -> dict:

    if not os.path.exists(
        _STORE_PATH
    ):
        return {}

    try:

        with open(
            _STORE_PATH,
            "r",
        ) as f:

            data = json.load(f)

        if not isinstance(
            data,
            dict,
        ):

            return {}

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # The old system created global clusters which mixed
        # repositories.
        #
        # Those records cannot safely be reused by the new
        # repository-aware system.
        #
        # Only repository-scoped records participate now.
        # ----------------------------------------------------

        scoped = {
            signature: record
            for signature, record
            in data.items()
            if (
                isinstance(
                    record,
                    dict,
                )
                and record.get(
                    "repository"
                )
            )
        }

        if len(scoped) != len(data):

            logger.info(
                "Ignoring %d legacy global "
                "cluster-review records.",
                len(data) - len(scoped),
            )

        return scoped

    except Exception as exc:

        logger.error(
            "Failed to load cluster review store: %s",
            exc,
        )

        return {}


def _save_store(
    store: dict,
):

    temporary_path = (
        f"{_STORE_PATH}.tmp"
    )

    with open(
        temporary_path,
        "w",
    ) as f:

        json.dump(
            store,
            f,
            indent=2,
        )

    os.replace(
        temporary_path,
        _STORE_PATH,
    )


# ============================================================
# SIGNATURE
# ============================================================

def _cluster_signature(
    ticket_ids: list[str],
    repository: str,
) -> str:
    """
    Repository-scoped deterministic identity.

    Example:

        kubernetes::ticketA|ticketB|ticketC

    and

        prometheus::ticketA|ticketB|ticketC

    can never be the same pattern.
    """

    ticket_part = "|".join(
        sorted(
            str(ticket_id)
            for ticket_id
            in ticket_ids
        )
    )

    return (
        f"{repository}::{ticket_part}"
    )


# ============================================================
# OVERLAP
# ============================================================

def _ticket_overlap(
    current_ids: set[str],
    stored_ids: set[str],
) -> float:

    if (
        not current_ids
        or not stored_ids
    ):
        return 0.0

    intersection = len(
        current_ids
        &
        stored_ids
    )

    union = len(
        current_ids
        |
        stored_ids
    )

    if union == 0:
        return 0.0

    return (
        intersection
        /
        union
    )


# ============================================================
# FIND EXISTING PATTERN
# ============================================================

def _find_existing_pattern(
    store: dict,
    ticket_ids: list[str],
    repository: str,
) -> tuple[
    Optional[str],
    float,
]:
    """
    Finds a previous pattern ONLY inside
    the same repository.
    """

    signature = (
        _cluster_signature(
            ticket_ids,
            repository,
        )
    )

    if signature in store:

        return (
            signature,
            1.0,
        )

    current_ids = set(
        ticket_ids
    )

    best_signature = None
    best_overlap = 0.0

    for (
        stored_signature,
        record,
    ) in store.items():

        # ----------------------------------------------------
        # THE CRITICAL SAFETY CHECK
        # ----------------------------------------------------

        if (
            record.get(
                "repository"
            )
            != repository
        ):

            continue

        stored_ids = set(
            record.get(
                "ticket_ids",
                [],
            )
        )

        overlap = (
            _ticket_overlap(
                current_ids,
                stored_ids,
            )
        )

        if overlap > best_overlap:

            best_overlap = (
                overlap
            )

            best_signature = (
                stored_signature
            )

    if (
        best_overlap
        >= 0.60
    ):

        return (
            best_signature,
            best_overlap,
        )

    return (
        None,
        0.0,
    )



_REPLACEMENT_SUMMARIES = {
    "Recurring pattern detected.",
    "Unclassified recurring issue",
}

_VALID_TYPES = {"Bug", "Security", "Performance", "Configuration"}


def _needs_reclassification(record: dict) -> bool:
    """Identify records created while cluster characterization was broken."""
    summary = str(record.get("summary", "")).strip()
    cluster_type = str(record.get("type", "")).strip()
    return (
        summary in _REPLACEMENT_SUMMARIES
        or not summary
        or cluster_type not in _VALID_TYPES
    )

# ============================================================
# RECONCILIATION
# ============================================================

def _reconcile_clusters_locked(
    clusters: list[dict],
) -> list[dict]:
    """
    Reconciles newly discovered repository-specific
    clusters with persistent human review patterns.

    Existing:

        label       -> preserved
        summary     -> preserved
        status      -> preserved
        repository  -> preserved

    New:

        receives new repository-scoped identity
        starts as pending
    """

    store = _load_store()

    now = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    reconciled = []

    matched_signatures = set()

    for cluster in clusters:

        ticket_ids = [
            str(
                ticket["id"]
            )

            for ticket
            in cluster.get(
                "tickets",
                [],
            )
        ]

        repository = str(
            cluster.get(
                "repository"
            )
            or "unknown"
        ).strip()

        if not repository:
            repository = "unknown"

        if not ticket_ids:
            continue

        current_signature = (
            _cluster_signature(
                ticket_ids,
                repository,
            )
        )

        existing_signature, overlap = (
            _find_existing_pattern(
                store,
                ticket_ids,
                repository,
            )
        )

        # ====================================================
        # EXISTING PATTERN
        # ====================================================

        if (
            existing_signature
            and
            existing_signature
            not in matched_signatures
        ):

            existing = store[
                existing_signature
            ]

            matched_signatures.add(
                existing_signature
            )

            # Human decisions remain persistent. However, records created
            # while characterization was failing may contain the old generic
            # summary/type. Those broken values are safe to repair from the
            # newly characterized cluster; an already meaningful label and
            # summary are left untouched.
            repair_characterization = _needs_reclassification(existing)

            if repair_characterization:
                existing["type"] = cluster.get("type", "Bug")
                existing["summary"] = cluster.get(
                    "summary",
                    "Recurring pattern detected.",
                )

            existing[
                "repository"
            ] = repository

            existing[
                "last_seen"
            ] = now

            existing[
                "size"
            ] = len(
                ticket_ids
            )

            existing[
                "ticket_ids"
            ] = ticket_ids

            existing[
                "latest_cluster_signature"
            ] = current_signature

            existing[
                "match_overlap"
            ] = round(
                overlap,
                4,
            )

            merged = dict(
                cluster
            )

            merged[
                "signature"
            ] = existing_signature

            merged[
                "summary"
            ] = existing.get(
                "summary",
                cluster.get(
                    "summary",
                    "Unclassified recurring issue",
                ),
            )

            merged[
                "type"
            ] = existing.get(
                "type",
                cluster.get(
                    "type",
                    "Bug",
                ),
            )

            merged[
                "status"
            ] = existing.get(
                "status",
                "pending",
            )

            merged[
                "repository"
            ] = repository

            merged[
                "first_seen"
            ] = existing.get(
                "first_seen",
                now,
            )

            merged[
                "last_seen"
            ] = existing.get(
                "last_seen",
                now,
            )

            reconciled.append(
                merged
            )

            logger.info(
                "Existing repository-scoped pattern preserved: "
                "repo='%s', label='%s', overlap=%.2f",
                repository,
                merged["type"],
                overlap,
            )

        # ====================================================
        # NEW PATTERN
        # ====================================================

        else:

            existing = {
                "signature":
                    current_signature,

                "repository":
                    repository,

                "summary":
                    cluster.get(
                        "summary",
                        "Unclassified recurring issue",
                    ),

                "type":
                    cluster.get(
                        "type",
                        "Bug",
                    ),

                "status":
                    "pending",

                "size":
                    len(
                        ticket_ids
                    ),

                "ticket_ids":
                    ticket_ids,

                "first_seen":
                    now,

                "last_seen":
                    now,

                "latest_cluster_signature":
                    current_signature,

                "match_overlap":
                    1.0,
            }

            store[
                current_signature
            ] = existing

            matched_signatures.add(
                current_signature
            )

            merged = dict(
                cluster
            )

            merged[
                "signature"
            ] = current_signature

            merged[
                "summary"
            ] = existing[
                "summary"
            ]

            merged[
                "type"
            ] = existing[
                "type"
            ]

            merged[
                "status"
            ] = "pending"

            merged[
                "repository"
            ] = repository

            merged[
                "first_seen"
            ] = now

            merged[
                "last_seen"
            ] = now

            reconciled.append(
                merged
            )

            logger.info(
                "NEW repository-scoped pattern: "
                "repo='%s', label='%s'",
                repository,
                existing["type"],
            )

    _save_store(
        store
    )

    return reconciled


def reconcile_clusters(
    clusters: list[dict],
) -> list[dict]:
    """Reconcile clusters atomically with human review decisions."""
    with _STORE_LOCK:
        return _reconcile_clusters_locked(clusters)


# ============================================================
# HUMAN REVIEW
# ============================================================

def set_review_status(
    signature: str,
    status: str,
) -> bool:

    if status not in {
        "approved",
        "rejected",
        "pending",
    }:
        raise ValueError(
            "status must be 'approved', 'rejected', or 'pending'"
        )

    # The scheduler also writes this JSON file. Holding the lock across
    # load -> modify -> save prevents a scheduler run from overwriting a
    # just-completed human decision.
    with _STORE_LOCK:
        store = _load_store()

        if signature not in store:
            return False

        store[signature]["status"] = status
        store[signature]["decided_at"] = datetime.now(
            timezone.utc
        ).isoformat()

        _save_store(store)

    logger.info(
        "Cluster %s... marked as '%s'",
        signature[:30],
        status,
    )

    return True


# ============================================================
# PUBLIC ACCESS
# ============================================================

def get_all_reviews() -> dict:
    with _STORE_LOCK:
        return _load_store()
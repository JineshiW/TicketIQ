import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler


logger = logging.getLogger("TicketIQ")


_scheduler = BackgroundScheduler()

# APScheduler's Job object does not expose last_run_time.
# We therefore track the actual execution ourselves.
_last_run_time = None


def run_clustering_job(
    qdrant_client,
):
    """
    Runs the recurring-pattern discovery pipeline.

    The scheduled job performs:
        1. clustering/discovery
        2. persistent pattern reconciliation

    The execution timestamp is tracked manually because
    APScheduler Job does not provide last_run_time.
    """

    global _last_run_time

    from clustering import build_cluster_response

    logger.info(
        "[Scheduled Job] Running automatic recurring pattern check..."
    )

    try:

        result = build_cluster_response(
            qdrant_client,
            force=True,
        )

        clusters = result.get(
            "clusters",
            [],
        )

        real_clusters = [
            cluster
            for cluster in clusters
            if cluster.get("cluster_id") != -1
        ]

        pending_count = sum(
            1
            for cluster in real_clusters
            if cluster.get("status") == "pending"
        )

        # Record the time ONLY after the clustering job
        # completed successfully.
        _last_run_time = datetime.now(timezone.utc)

        logger.info(
            "[Scheduled Job] Done. "
            "%d persistent clusters returned, "
            "%d pending review.",
            len(real_clusters),
            pending_count,
        )

    except Exception as exc:

        logger.exception(
            "[Scheduled Job] Failed: %s",
            exc,
        )


def start_scheduler(
    qdrant_client,
    interval_hours: float = 1.0,
):

    if not _scheduler.running:

        _scheduler.add_job(
            run_clustering_job,
            "interval",
            hours=interval_hours,
            args=[
                qdrant_client
            ],
            id="recurring_pattern_check",
            replace_existing=True,
            # Prime the cache once when the server starts. Subsequent
            # executions happen hourly. The API itself never performs
            # this expensive work on normal GET /clusters requests.
            next_run_time=datetime.now(timezone.utc),
        )

        _scheduler.start()

        logger.info(
            "Background scheduler started "
            "(every %.1f hours).",
            interval_hours,
        )


def stop_scheduler():

    if _scheduler.running:

        _scheduler.shutdown(
            wait=False
        )

        logger.info(
            "Background scheduler stopped."
        )


def get_scheduler_status():
    """
    Returns the current background scheduler status.

    APScheduler provides next_run_time on Job, but not
    last_run_time. The latter is therefore tracked manually
    by run_clustering_job().
    """

    job = _scheduler.get_job(
        "recurring_pattern_check"
    )

    if job is None:

        return {
            "running": _scheduler.running,
            "scheduled": False,
            "last_run_time": (
                _last_run_time.isoformat()
                if _last_run_time
                else None
            ),
            "next_run_time": None,
        }

    return {
        "running": _scheduler.running,
        "scheduled": True,

        "last_run_time": (
            _last_run_time.isoformat()
            if _last_run_time
            else None
        ),

        "next_run_time": (
            job.next_run_time.isoformat()
            if job.next_run_time
            else None
        ),
    }
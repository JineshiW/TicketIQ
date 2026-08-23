from langchain_core.tools import tool

from assets.shared_resources import qdrant_client


# ============================================================
# TOOL — RECURRING PATTERN DETECTION
# ============================================================

@tool
def check_recurring_patterns() -> str:
    """
    Analyzes the full Qdrant ticket database for recurring
    patterns and clusters.

    This tool ONLY detects recurring patterns.

    It does not perform any automatic action.

    Any detected pattern requires human review.
    """

    # --------------------------------------------------------
    # Import clustering only when the tool is actually used.
    #
    # This prevents clustering.py from becoming part of the
    # application import chain during server startup.
    # --------------------------------------------------------

    from clustering import build_cluster_response

    # --------------------------------------------------------
    # Run clustering
    # --------------------------------------------------------

    result = build_cluster_response(
        qdrant_client
    )

    clusters = result.get(
        "clusters",
        [],
    )

    # --------------------------------------------------------
    # Keep only meaningful clusters
    # --------------------------------------------------------

    significant = [
        cluster
        for cluster in clusters
        if (
            cluster.get("cluster_id") != -1
            and cluster.get("size", 0) >= 3
        )
    ]

    # --------------------------------------------------------
    # No meaningful patterns
    # --------------------------------------------------------

    if not significant:
        return (
            "No significant recurring "
            "patterns detected."
        )

    # --------------------------------------------------------
    # Format results
    # --------------------------------------------------------

    summary_lines = []

    for cluster in significant:

        cluster_id = cluster.get(
            "cluster_id",
            "unknown",
        )

        size = cluster.get(
            "size",
            0,
        )

        summary = cluster.get(
            "summary",
            "No summary available.",
        )

        cluster_type = cluster.get(
            "type",
            "Unknown",
        )

        summary_lines.append(
            f"Cluster {cluster_id}: "
            f"{size} tickets - "
            f"{summary} "
            f"(Type: {cluster_type}) "
            f"[REQUIRES HUMAN REVIEW]"
        )

    return "\n".join(summary_lines)
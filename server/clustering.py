import logging
import json
import threading
import numpy as np

from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA

import hdbscan
import ollama

from assets.vectors.domain_terms import vector_prompt_hint


logger = logging.getLogger("TicketIQ")


# Server-side cache for the last completed recurring-pattern result.
# Normal GET /clusters requests must not rerun clustering.
_CLUSTER_CACHE = None
_CLUSTER_CACHE_LOCK = threading.RLock()
_CLUSTER_COMPUTE_LOCK = threading.Lock()


def _get_cached_cluster_response():
    with _CLUSTER_CACHE_LOCK:
        return _CLUSTER_CACHE


def _set_cached_cluster_response(result: dict):
    global _CLUSTER_CACHE
    with _CLUSTER_CACHE_LOCK:
        _CLUSTER_CACHE = result


# ============================================================
# LOAD ALL TICKET DATA
# ============================================================

def get_all_ticket_data(
    qdrant_client,
    collection_name: str,
) -> dict:
    """
    Loads every ticket from Qdrant.

    IMPORTANT:
    source_repo is preserved because recurring-pattern clustering
    is now performed independently for each repository.
    """

    ids = []
    embeddings = []
    metadatas = []

    next_offset = None

    while True:

        points, next_offset = qdrant_client.scroll(
            collection_name=collection_name,
            with_payload=True,
            with_vectors=True,
            limit=250,
            offset=next_offset,
        )

        for point in points:

            payload = point.payload or {}

            ids.append(
                payload.get(
                    "ticket_id",
                    str(point.id),
                )
            )

            embeddings.append(
                point.vector
            )

            metadatas.append(
                payload
            )

        if next_offset is None:
            break

    return {
        "ids": ids,
        "embeddings": np.array(
            embeddings
        ),
        "metadatas": metadatas,
    }


# ============================================================
# CLUSTERING ALGORITHM COMPARISON
# ============================================================

def run_clustering_comparison(
    embeddings: np.ndarray,
) -> dict:
    """
    Runs DBSCAN, K-means and HDBSCAN.

    IMPORTANT:
    This function now receives tickets from ONE repository only.

    Therefore algorithm selection is performed independently for
    each repository.
    """

    n_samples = len(
        embeddings
    )

    results = {}

    if n_samples < 4:

        return {
            "comparison": {},
            "best_algorithm": None,
            "labels": np.full(
                n_samples,
                -1,
                dtype=int,
            ),
        }

    # --------------------------------------------------------
    # DBSCAN
    # --------------------------------------------------------

    try:

        dbscan_labels = DBSCAN(
            eps=0.5,
            min_samples=2,
            metric="cosine",
        ).fit_predict(
            embeddings
        )

        n_clusters = (
            len(
                set(
                    dbscan_labels
                )
            )
            -
            (
                1
                if -1 in dbscan_labels
                else 0
            )
        )

        score = (
            silhouette_score(
                embeddings,
                dbscan_labels,
            )
            if n_clusters >= 2
            else -1.0
        )

        results["dbscan"] = {
            "labels": dbscan_labels,
            "silhouette": score,
            "n_clusters": n_clusters,
        }

        logger.info(
            "DBSCAN: %d clusters, silhouette=%.3f",
            n_clusters,
            score,
        )

    except Exception as exc:

        logger.warning(
            "DBSCAN failed: %s",
            exc,
        )

        results["dbscan"] = {
            "labels": None,
            "silhouette": -1.0,
            "n_clusters": 0,
        }

    # --------------------------------------------------------
    # K-MEANS
    # --------------------------------------------------------

    try:

        k = max(
            2,
            min(
                8,
                n_samples // 5,
            ),
        )

        kmeans_labels = KMeans(
            n_clusters=k,
            random_state=42,
            n_init=10,
        ).fit_predict(
            embeddings
        )

        score = silhouette_score(
            embeddings,
            kmeans_labels,
        )

        results["kmeans"] = {
            "labels": kmeans_labels,
            "silhouette": score,
            "n_clusters": k,
        }

        logger.info(
            "K-means: %d clusters, silhouette=%.3f",
            k,
            score,
        )

    except Exception as exc:

        logger.warning(
            "K-means failed: %s",
            exc,
        )

        results["kmeans"] = {
            "labels": None,
            "silhouette": -1.0,
            "n_clusters": 0,
        }

    # --------------------------------------------------------
    # HDBSCAN
    # --------------------------------------------------------

    try:

        hdb_labels = (
            hdbscan.HDBSCAN(
                min_cluster_size=2,
                metric="euclidean",
            )
            .fit_predict(
                embeddings
            )
        )

        n_clusters = (
            len(
                set(
                    hdb_labels
                )
            )
            -
            (
                1
                if -1 in hdb_labels
                else 0
            )
        )

        score = (
            silhouette_score(
                embeddings,
                hdb_labels,
            )
            if n_clusters >= 2
            else -1.0
        )

        results["hdbscan"] = {
            "labels": hdb_labels,
            "silhouette": score,
            "n_clusters": n_clusters,
        }

        logger.info(
            "HDBSCAN: %d clusters, silhouette=%.3f",
            n_clusters,
            score,
        )

    except Exception as exc:

        logger.warning(
            "HDBSCAN failed: %s",
            exc,
        )

        results["hdbscan"] = {
            "labels": None,
            "silhouette": -1.0,
            "n_clusters": 0,
        }

    # --------------------------------------------------------
    # SELECT BEST ALGORITHM
    # --------------------------------------------------------

    best_algorithm = max(
        results,
        key=lambda key:
            results[key]["silhouette"],
    )

    logger.info(
        "Best algorithm: %s",
        best_algorithm,
    )

    return {
        "comparison": {
            key: {
                "silhouette": value[
                    "silhouette"
                ],
                "n_clusters": value[
                    "n_clusters"
                ],
            }
            for key, value in results.items()
        },
        "best_algorithm": best_algorithm,
        "labels": results[
            best_algorithm
        ]["labels"],
    }


# ============================================================
# OLLAMA CLUSTER CHARACTERIZATION
# ============================================================

def _fallback_cluster_characterization(tickets: list[dict]) -> dict:
    """Return a useful local classification if Ollama output is unavailable.

    This is deliberately only a fallback. The normal path remains the
    llama3.2 classification above. The fallback prevents a failed/truncated
    model response from turning every cluster into the generic Bug label.
    """
    import re

    text = " ".join(
        str(ticket.get("title", ""))
        for ticket in tickets[:6]
    ).lower()

    scores = {
        "Security": 0,
        "Performance": 0,
        "Configuration": 0,
        "Bug": 0,
    }

    keywords = {
        "Security": (
            "security", "vulnerability", "cve", "exploit", "permission",
            "rbac", "auth", "authentication", "authorization", "token",
            "credential", "secret", "privilege", "access control",
        ),
        "Performance": (
            "performance", "slow", "latency", "timeout", "memory",
            "cpu", "leak", "throughput", "benchmark", "hang", "freeze",
            "lag", "scalability", "resource", "high load", "crashloop",
        ),
        "Configuration": (
            "configuration", "config", "setting", "option", "flag",
            "parameter", "environment", "env", "yaml", "json", "setup",
            "install", "deployment", "deploy", "configure",
        ),
        "Bug": (
            "bug", "error", "incorrect", "wrong", "broken", "fail",
            "failure", "crash", "exception", "issue", "does not work",
            "not working", "regression",
        ),
    }

    for category, words in keywords.items():
        for word in words:
            if re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", text):
                scores[category] += 2 if " " in word else 1

    cluster_type = max(scores, key=scores.get)

    # If there is genuinely no signal, keep Bug as the conservative fallback
    # because the four-category schema has no "Unknown" value.
    if scores[cluster_type] == 0:
        cluster_type = "Bug"

    titles = [
        str(ticket.get("title", "")).strip().rstrip(".")
        for ticket in tickets[:2]
        if str(ticket.get("title", "")).strip()
    ]

    if titles:
        summary = titles[0]
        if len(summary) > 110:
            summary = summary[:107].rstrip() + "..."
    else:
        summary = f"Recurring {cluster_type.lower()} issue"

    return {
        "summary": summary,
        "type": cluster_type,
    }


def characterize_clusters_batch(
    cluster_groups: dict[int, list[dict]],
) -> dict[int, dict]:
    """Classify repository-local clusters with llama3.2.

    The previous implementation put every cluster into one large JSON
    response but limited Ollama to only 700 output tokens. With dozens of
    clusters, the response was truncated; the parser then returned no
    usable records and the fallback assigned every cluster the same
    ``Bug`` / ``Recurring pattern detected.`` values.

    We keep the same single-model architecture, but split the work into
    small batches. This makes the JSON response reliably complete while
    retaining the existing repository-aware clustering and cache/review
    behaviour.
    """
    real_clusters = {
        int(label): tickets
        for label, tickets in cluster_groups.items()
        if int(label) != -1
    }

    if not real_clusters:
        return {}

    vector_hint = vector_prompt_hint()
    results: dict[int, dict] = {}
    cluster_items = list(real_clusters.items())

    # 10 clusters per request is small enough for reliable JSON while
    # avoiding one enormous prompt/output for a repository run.
    batch_size = 10

    for batch_start in range(0, len(cluster_items), batch_size):
        batch = cluster_items[batch_start:batch_start + batch_size]
        compact_clusters = []

        for label, tickets in batch:
            repository = tickets[0].get("source_repo", "unknown")
            titles = [
                str(ticket.get("title", "")).strip()[:220]
                for ticket in tickets[:4]
                if str(ticket.get("title", "")).strip()
            ]
            compact_clusters.append({
                "id": int(label),
                "repository": repository,
                "titles": titles,
            })

        prompt = f"""You classify recurring technical support-ticket clusters.
Each cluster is already isolated to one repository.

Allowed types: Bug, Security, Performance, Configuration.
Return ONLY valid JSON in this exact shape:
{{"clusters":[{{"id":0,"summary":"short common issue","type":"Bug"}}]}}

Rules:
- Include EVERY cluster ID exactly once.
- Summary must describe the common technical issue in 6-14 words.
- Type must be exactly one of: Bug, Security, Performance, Configuration.
- Use the dominant problem shown by the ticket titles.
- Do not use "Recurring pattern detected." as a summary.
- Do not classify every cluster as Bug unless the titles actually indicate bugs.
- Do not invent details.

Known technical vocabulary:
{vector_hint}

Clusters:
{json.dumps(compact_clusters, ensure_ascii=False)}
"""

        try:
            response = ollama.chat(
                model="llama3.2:latest",
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={
                    "temperature": 0,
                    # 10 clusters x short summaries/types comfortably fit here.
                    "num_predict": 900,
                },
                keep_alive="10m",
            )

            content = str(response["message"]["content"]).strip()
            parsed = json.loads(content)
            items = parsed.get("clusters", []) if isinstance(parsed, dict) else []

            for item in items:
                if not isinstance(item, dict):
                    continue

                try:
                    label = int(item.get("id"))
                except (TypeError, ValueError):
                    continue

                if label not in real_clusters:
                    continue

                cluster_type = str(item.get("type", "")).strip()
                if cluster_type not in {"Bug", "Security", "Performance", "Configuration"}:
                    continue

                summary = str(item.get("summary", "")).strip()
                if not summary or summary.lower() == "recurring pattern detected.":
                    continue

                results[label] = {
                    "summary": summary,
                    "type": cluster_type,
                }

        except Exception as exc:
            logger.warning(
                "Cluster characterization batch %d failed: %s",
                batch_start // batch_size + 1,
                exc,
            )

        # Fill only missing IDs from this batch. A model failure therefore
        # cannot collapse all missing clusters into Bug/generic text.
        for label, tickets in batch:
            if label not in results:
                results[label] = _fallback_cluster_characterization(tickets)

    return results


# ============================================================
# FULL REPOSITORY-AWARE PIPELINE
# ============================================================

def _compute_cluster_response(
    qdrant_client,
) -> dict:
    """
    Repository-aware recurring-pattern pipeline.

    Flow:

        Qdrant
           ↓
        group by source_repo
           ↓
        cluster repository independently
           ↓
        characterize clusters with Ollama
           ↓
        reconcile with persistent review store
           ↓
        return all repository-specific clusters

    Therefore:

        Kubernetes Bug
        and
        Prometheus Bug

    are separate recurring patterns.
    """

    from assets.shared_resources import (
        COLLECTION_NAME,
    )

    from backgroundJobs.review_store import (
        reconcile_clusters,
    )

    # ========================================================
    # STEP 1 — LOAD EVERYTHING
    # ========================================================

    data = get_all_ticket_data(
        qdrant_client,
        COLLECTION_NAME,
    )

    embeddings = data[
        "embeddings"
    ]

    metadatas = data[
        "metadatas"
    ]

    if len(embeddings) < 4:

        return {
            "error":
                "Not enough tickets to cluster "
                "meaningfully. Need at least 4.",

            "clusters": [],
            "comparison": {},
            "best_algorithm": None,
            "repositories": [],
        }

    # ========================================================
    # STEP 2 — SPLIT BY REPOSITORY
    # ========================================================

    repository_indices = {}

    for index, metadata in enumerate(
        metadatas
    ):

        repository = str(
            metadata.get(
                "source_repo"
            )
            or
            "unknown"
        ).strip()

        if not repository:
            repository = "unknown"

        repository_indices.setdefault(
            repository,
            [],
        ).append(
            index
        )

    logger.info(
        "Found %d repositories for recurring-pattern clustering.",
        len(repository_indices),
    )

    raw_clusters = []

    repository_comparisons = {}

    global_cluster_id = 0

    # ========================================================
    # STEP 3 — CLUSTER EACH REPOSITORY
    # ========================================================

    for repository in sorted(
        repository_indices
    ):

        indices = (
            repository_indices[
                repository
            ]
        )

        repo_embeddings = (
            embeddings[
                indices
            ]
        )

        logger.info(
            "Clustering repository '%s' "
            "with %d tickets.",
            repository,
            len(indices),
        )

        if len(repo_embeddings) < 4:

            logger.info(
                "Skipping repository '%s' "
                "because it contains fewer than 4 tickets.",
                repository,
            )

            repository_comparisons[
                repository
            ] = {
                "comparison": {},
                "best_algorithm": None,
            }

            continue

        clustering_result = (
            run_clustering_comparison(
                repo_embeddings
            )
        )

        repository_comparisons[
            repository
        ] = {
            "comparison":
                clustering_result[
                    "comparison"
                ],

            "best_algorithm":
                clustering_result[
                    "best_algorithm"
                ],
        }

        labels = (
            clustering_result[
                "labels"
            ]
        )

        # ----------------------------------------------------
        # PCA is also repository-local.
        # ----------------------------------------------------

        coords_2d = (
            PCA(
                n_components=2
            )
            .fit_transform(
                repo_embeddings
            )
        )

        local_groups = {}

        for local_index, local_label in (
            enumerate(labels)
        ):

            local_label = int(
                local_label
            )

            original_index = (
                indices[
                    local_index
                ]
            )

            metadata = (
                metadatas[
                    original_index
                ]
            )

            local_groups.setdefault(
                local_label,
                [],
            ).append(
                {
                    "id":
                        data["ids"][
                            original_index
                        ],

                    "title":
                        metadata.get(
                            "title",
                            "",
                        ),

                    "resolution":
                        metadata.get(
                            "resolution",
                            "",
                        ),

                    "source_repo":
                        repository,

                    "x":
                        float(
                            coords_2d[
                                local_index
                            ][0]
                        ),

                    "y":
                        float(
                            coords_2d[
                                local_index
                            ][1]
                        ),
                }
            )

        # ----------------------------------------------------
        # Convert local clusters into globally unique
        # presentation clusters.
        # ----------------------------------------------------

        for local_label, tickets in (
            local_groups.items()
        ):

            if local_label == -1:

                raw_clusters.append(
                    {
                        "cluster_id": -1,

                        "cluster_key":
                            f"{repository}::unclustered",

                        "repository":
                            repository,

                        "summary":
                            "These tickets did not "
                            "match a recurring pattern.",

                        "type":
                            "Unclustered",

                        "status":
                            "pending",

                        "size":
                            len(tickets),

                        "tickets":
                            tickets,
                    }
                )

                continue

            raw_clusters.append(
                {
                    "cluster_id":
                        global_cluster_id,

                    "cluster_key":
                        f"{repository}::cluster::{global_cluster_id}",

                    "repository":
                        repository,

                    "local_cluster_id":
                        local_label,

                    "summary":
                        "Unclassified recurring issue",

                    "type":
                        "Bug",

                    "status":
                        "pending",

                    "size":
                        len(tickets),

                    "tickets":
                        tickets,
                }
            )

            global_cluster_id += 1

    # ========================================================
    # STEP 4 — CHARACTERIZE CLUSTERS
    # ========================================================

    cluster_groups = {
        cluster["cluster_id"]:
            cluster["tickets"]
        for cluster in raw_clusters
        if cluster["cluster_id"] != -1
    }

    characterizations = (
        characterize_clusters_batch(
            cluster_groups
        )
    )

    for cluster in raw_clusters:

        if cluster[
            "cluster_id"
        ] == -1:

            continue

        characterization = (
            characterizations.get(
                cluster["cluster_id"],
                {
                    "summary":
                        "Unclassified recurring issue",
                    "type":
                        "Bug",
                },
            )
        )

        cluster[
            "summary"
        ] = characterization.get(
            "summary",
            "Unclassified recurring issue",
        )

        cluster[
            "type"
        ] = characterization.get(
            "type",
            "Bug",
        )

    # ========================================================
    # STEP 5 — ONLY PERSIST REAL CLUSTERS
    # ========================================================

    real_clusters = [
        cluster
        for cluster in raw_clusters
        if (
            cluster["cluster_id"]
            != -1
            and cluster["size"]
            >= 3
        )
    ]

    reconciled = (
        reconcile_clusters(
            real_clusters
        )
    )

    # ========================================================
    # STEP 6 — KEEP UNCLUSTERED REPOSITORY GROUPS
    # ========================================================

    unclustered = [
        cluster
        for cluster in raw_clusters
        if cluster["cluster_id"] == -1
    ]

    final_clusters = (
        reconciled
        + unclustered
    )

    # ========================================================
    # STEP 7 — STABLE ORDERING
    # ========================================================

    final_clusters.sort(
        key=lambda cluster: (
            cluster.get(
                "repository",
                "",
            ),

            cluster.get(
                "cluster_id"
            ) == -1,

            -cluster.get(
                "size",
                0,
            ),
        )
    )

    # ========================================================
    # STEP 8 — AGGREGATE ALGORITHM COMPARISON
    # ========================================================

    aggregate = {}

    for repository_result in (
        repository_comparisons.values()
    ):

        for algorithm, metrics in (
            repository_result[
                "comparison"
            ].items()
        ):

            entry = aggregate.setdefault(
                algorithm,
                {
                    "weighted_silhouette":
                        0.0,

                    "weight":
                        0,

                    "n_clusters":
                        0,
                },
            )

            weight = max(
                metrics[
                    "n_clusters"
                ],
                1,
            )

            entry[
                "weighted_silhouette"
            ] += (
                metrics[
                    "silhouette"
                ]
                * weight
            )

            entry[
                "weight"
            ] += weight

            entry[
                "n_clusters"
            ] += metrics[
                "n_clusters"
            ]

    comparison = {
        algorithm: {
            "silhouette":
                value[
                    "weighted_silhouette"
                ]
                /
                value["weight"]
                if value["weight"]
                else -1.0,

            "n_clusters":
                value[
                    "n_clusters"
                ],
        }

        for algorithm, value
        in aggregate.items()
    }

    best_algorithm = (
        max(
            comparison,
            key=lambda key:
                comparison[key][
                    "silhouette"
                ],
        )
        if comparison
        else None
    )

    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    result = {
        "clusters": final_clusters,
        "comparison": comparison,
        "best_algorithm": best_algorithm,
        "repositories": sorted(repository_indices),
        "repository_comparison": repository_comparisons,
    }

    _set_cached_cluster_response(result)
    return result


def build_cluster_response(
    qdrant_client,
    force: bool = False,
) -> dict:
    """Return the latest completed recurring-pattern result.

    Normal reads are cache-only. The hourly scheduler passes force=True
    to perform the expensive recomputation. This prevents tab navigation,
    browser refreshes and review actions from rerunning clustering/Ollama.
    """
    if not force:
        cached = _get_cached_cluster_response()
        if cached is not None:
            return cached

    # Prevent a browser request and the hourly worker from performing the
    # same expensive computation at the same time.
    with _CLUSTER_COMPUTE_LOCK:
        if not force:
            cached = _get_cached_cluster_response()
            if cached is not None:
                return cached
        return _compute_cluster_response(qdrant_client)

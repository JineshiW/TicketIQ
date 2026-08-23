"""
Backfill source_repo payload metadata for
existing Qdrant tickets.

The GitHub importer prefixes ticket IDs with
the repository short name.

Example:

kubernetes-141293
prometheus-12345
grafana-9876
"""

from assets.shared_resources import (
    qdrant_client,
    COLLECTION_NAME,
)


REPOSITORY_BY_PREFIX = {

    "kubernetes":
        "kubernetes/kubernetes",

    "spring-boot":
        "spring-projects/spring-boot",

    "elasticsearch":
        "elastic/elasticsearch",

    "vscode":
        "microsoft/vscode",

    "redis":
        "redis/redis",

    "prometheus":
        "prometheus/prometheus",

    "grafana":
        "grafana/grafana",

    "react":
        "facebook/react",

    "compose":
        "docker/compose",

    "node":
        "nodejs/node",
}


def infer_repository(
    ticket_id: str,
):

    prefix = (
        ticket_id
        .split("-", 1)[0]
        .lower()
    )

    return REPOSITORY_BY_PREFIX.get(
        prefix
    )


def main():

    offset = None

    updated = 0
    skipped = 0

    while True:

        points, next_offset = (
            qdrant_client.scroll(
                collection_name=(
                    COLLECTION_NAME
                ),
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
        )

        if not points:
            break

        for point in points:

            payload = (
                point.payload or {}
            )

            if payload.get(
                "source_repo"
            ):
                continue

            repository = infer_repository(
                str(
                    payload.get(
                        "ticket_id",
                        "",
                    )
                )
            )

            if not repository:

                skipped += 1

                print(
                    f"Skipping {point.id}: "
                    "cannot infer repository"
                )

                continue

            qdrant_client.set_payload(
                collection_name=(
                    COLLECTION_NAME
                ),
                payload={
                    "source_repo":
                        repository
                },
                points=[
                    point.id
                ],
            )

            updated += 1

        offset = next_offset

        if offset is None:
            break

    print(
        "Repository metadata "
        f"backfill complete. "
        f"Updated={updated}, "
        f"skipped={skipped}"
    )


if __name__ == "__main__":
    main()
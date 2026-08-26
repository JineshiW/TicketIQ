"""
Semantic-search tools for TicketIQ.

Workflow:

    Ollama
        |
        v
    SentenceTransformer
        |
        v
    Qdrant repository-filtered search
        |
        v
    Ollama summary

Qdrant is the source of truth for the repositories currently
available in the ticket database.
"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool
from langchain_ollama import ChatOllama

from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
)

from assets.shared_resources import (
    embedder,
    qdrant_client,
    COLLECTION_NAME,
)


logger = logging.getLogger("TicketIQ")


# ============================================================
# OLLAMA MODEL
# ============================================================

llm = ChatOllama(
    model="llama3.1:latest",
    temperature=0,
    num_predict=256,
    keep_alive="10m",
)

# ============================================================
# REPOSITORY DISCOVERY
# ============================================================

def get_supported_repositories() -> list[str]:
    """
    Dynamically discovers all repositories currently stored
    in the Qdrant collection.

    This is deliberately a function rather than a global
    constant because tickets can be imported after the
    application starts.
    """

    repositories = set()

    try:

        offset = None

        while True:

            points, next_offset = qdrant_client.scroll(
                collection_name=COLLECTION_NAME,
                offset=offset,
                limit=256,
                with_payload=True,
                with_vectors=False,
            )

            for point in points:

                payload = point.payload or {}

                repository = payload.get(
                    "source_repo"
                )

                if repository:

                    repository = str(
                        repository
                    ).strip()

                    if repository:
                        repositories.add(
                            repository
                        )

            if next_offset is None:
                break

            offset = next_offset

    except Exception as exc:

        logger.exception(
            "Unable to discover repositories from Qdrant: %s",
            exc,
        )

        return []

    result = sorted(
        repositories
    )

    logger.info(
        "Supported repositories discovered: %s",
        result,
    )

    return result


# ============================================================
# OLLAMA TOOL
# ============================================================

@tool
def ollama_ticket_tool(
    operation: str,
    title: str = "",
    description: str = "",
    normalized_text: str = "",
    repository: str = "",
    search_results: str = "",
) -> str:
    """
    Uses Ollama for ticket understanding and explanation.

    operation:

        normalize
            Understand and normalize a new ticket and select
            the most relevant repository.

        summarize
            Explain the historical Qdrant matches.
    """

    # ========================================================
    # NORMALIZATION
    # ========================================================

    if operation == "normalize":

        repositories = get_supported_repositories()

        if not repositories:

            raise RuntimeError(
                "No repositories are currently stored in Qdrant."
            )

        repositories_json = json.dumps(
            repositories,
            indent=2,
        )

        prompt = f"""
You are TicketIQ's ticket-analysis component.

Analyze the following new support ticket.

TITLE:
{title}

DESCRIPTION:
{description}

AVAILABLE REPOSITORIES:

{repositories_json}

Your tasks:

1. Understand the technical problem.
2. Remove unnecessary wording.
3. Produce a concise technical issue statement.
4. Identify the ONE most relevant repository.
5. The repository MUST be selected from the supplied list.
6. NEVER invent a repository.
7. Return ONLY valid JSON.
8. Do not include markdown.
9. Do not include explanations outside the JSON.

Return exactly:

{{
    "normalized_text": "concise technical issue statement",
    "quality": "sufficient",
    "repository": "exact repository name from the list"
}}

The quality value MUST be one of:

- insufficient
- low_detail
- sufficient

AVAILABLE REPOSITORIES:
{repositories_json}
"""

        response = llm.invoke(
            prompt
        )

        content = response.content

        if not isinstance(
            content,
            str,
        ):
            content = str(content)

        content = content.strip()

        # ----------------------------------------------------
        # Parse JSON
        # ----------------------------------------------------

        try:

            parsed = json.loads(
                content
            )

        except json.JSONDecodeError:

            start = content.find("{")
            end = content.rfind("}")

            if (
                start == -1
                or end == -1
            ):

                raise RuntimeError(
                    "Ollama normalization did not return valid JSON."
                )

            try:

                parsed = json.loads(
                    content[
                        start:end + 1
                    ]
                )

            except json.JSONDecodeError as exc:

                raise RuntimeError(
                    "Ollama returned malformed JSON "
                    "during normalization."
                ) from exc

        # ----------------------------------------------------
        # Extract normalized text
        # ----------------------------------------------------

        normalized = parsed.get(
            "normalized_text"
        )

        if not normalized:

            raise RuntimeError(
                "Ollama normalization did not return normalized_text."
            )

        normalized = str(
            normalized
        ).strip()

        # ----------------------------------------------------
        # Extract quality
        # ----------------------------------------------------

        quality = parsed.get(
            "quality",
            "sufficient",
        )

        if quality not in {
            "insufficient",
            "low_detail",
            "sufficient",
        }:

            quality = "sufficient"

        # ----------------------------------------------------
        # Extract repository
        # ----------------------------------------------------

        repository = parsed.get(
            "repository"
        )

        if repository is None:

            repository = ""

        repository = str(
            repository
        ).strip()

        # ----------------------------------------------------
        # Case-insensitive repository matching
        # ----------------------------------------------------

        repository_map = {
            str(repo).lower(): repo
            for repo in repositories
        }

        repository = repository_map.get(
            repository.lower(),
            "",
        )

        # ----------------------------------------------------
        # If Ollama failed to select a repository, try a
        # simple textual fallback before failing.
        # ----------------------------------------------------

        if not repository:

            combined_text = (
                f"{title} {description} {normalized}"
            ).lower()

            # Exact repository-name references in the ticket
            # are preferred as a fallback.
            for repo in repositories:

                repo_lower = repo.lower()

                if repo_lower in combined_text:

                    repository = repo

                    logger.info(
                        "Repository fallback selected: %s",
                        repository,
                    )

                    break

        # ----------------------------------------------------
        # Final validation
        # ----------------------------------------------------

        if not repository:

            raise RuntimeError(
                "Ollama did not identify a valid repository "
                "from the repositories currently stored in Qdrant."
            )

        return json.dumps(
            {
                "normalized_text": normalized,
                "quality": quality,
                "repository": repository,
            }
        )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    if operation == "summarize":

        prompt = f"""
You are TicketIQ's final semantic-search explanation model.

A new support ticket was normalized and searched against
historical tickets.

SELECTED REPOSITORY:
{repository}

NORMALIZED NEW TICKET:
{normalized_text}

HISTORICAL SEARCH RESULTS:
{search_results}

Explain the historical evidence for the new ticket.

Rules:

1. ONLY discuss the selected repository.
2. ONLY use information contained in the historical search results.
3. DO NOT invent resolutions.
4. DO NOT mix repositories.
5. If there are no useful matches, clearly say that historical
   evidence is unavailable or weak.
6. Identify the most relevant historical ticket when possible.
7. Explain its resolution when one is available.
8. Mention similarity scores when useful.
9. Do not claim that a historical resolution is guaranteed
   to solve the new ticket.
10. Return ONLY valid JSON.
11. Do not use markdown outside the JSON.

Return exactly:

{{
    "summary": "clear explanation of the historical evidence"
}}
"""

        response = llm.invoke(
            prompt
        )

        content = response.content

        if not isinstance(
            content,
            str,
        ):
            content = str(content)

        content = content.strip()

        # ----------------------------------------------------
        # Parse JSON
        # ----------------------------------------------------

        try:

            parsed = json.loads(
                content
            )

        except json.JSONDecodeError:

            start = content.find("{")
            end = content.rfind("}")

            if (
                start == -1
                or end == -1
            ):

                return json.dumps(
                    {
                        "summary": content
                    }
                )

            try:

                parsed = json.loads(
                    content[
                        start:end + 1
                    ]
                )

            except json.JSONDecodeError:

                return json.dumps(
                    {
                        "summary": content
                    }
                )

        summary = parsed.get(
            "summary",
            "",
        )

        if not summary:

            summary = (
                "No historical explanation was generated."
            )

        return json.dumps(
            {
                "summary": str(
                    summary
                )
            }
        )

    # ========================================================
    # INVALID OPERATION
    # ========================================================

    raise ValueError(
        "operation must be either "
        "'normalize' or 'summarize'."
    )


# ============================================================
# SENTENCE TRANSFORMER TOOL
# ============================================================

@tool
def sentence_transformer_tool(
    normalized_text: str,
) -> str:
    """
    Generates a 384-dimensional SentenceTransformer embedding.

    The actual embedding vector is returned directly.
    No embedding ID is used.
    """

    if not normalized_text.strip():

        raise ValueError(
            "normalized_text cannot be empty."
        )

    embedding = embedder.encode(
        normalized_text
    ).tolist()

    dimensions = len(
        embedding
    )

    logger.info(
        "SentenceTransformer generated embedding "
        "with %d dimensions.",
        dimensions,
    )

    if dimensions != 384:

        logger.warning(
            "Expected a 384-dimensional embedding, "
            "but received %d dimensions.",
            dimensions,
        )

    return json.dumps(
        {
            "embedding": embedding,
            "dimensions": dimensions,
        }
    )


# ============================================================
# QDRANT REPOSITORY-SCOPED SEARCH
# ============================================================

@tool
def search_repository_tickets(
    repository: str,
    embedding: str,
) -> str:
    """
    Searches Qdrant for semantically similar historical tickets.

    IMPORTANT:

    The Qdrant search is physically restricted to the selected
    repository using a payload filter on `source_repo`.

    Ollama does NOT control which tickets are returned.
    Qdrant enforces the repository restriction.
    """

    # ========================================================
    # DISCOVER CURRENT REPOSITORIES
    # ========================================================

    repositories = get_supported_repositories()

    if not repositories:

        raise RuntimeError(
            "No repositories are currently available in Qdrant."
        )

    # ========================================================
    # VALIDATE REPOSITORY
    # ========================================================

    repository = str(
        repository
    ).strip()

    repository_map = {
        str(repo).lower(): repo
        for repo in repositories
    }

    repository = repository_map.get(
        repository.lower()
    )

    if not repository:

        raise ValueError(
            "Requested repository is not currently present "
            "in Qdrant."
        )

    # ========================================================
    # PARSE EMBEDDING
    # ========================================================

    try:

        vector = json.loads(
            embedding
        )

    except (
        json.JSONDecodeError,
        TypeError,
    ) as exc:

        raise ValueError(
            "embedding must contain a valid JSON array."
        ) from exc

    if not isinstance(
        vector,
        list,
    ):

        raise ValueError(
            "embedding must be a JSON list."
        )

    if not vector:

        raise ValueError(
            "embedding cannot be empty."
        )

    # ========================================================
    # VALIDATE DIMENSION
    # ========================================================

    if len(vector) != 384:

        raise ValueError(
            f"Expected a 384-dimensional embedding, "
            f"but received {len(vector)} dimensions."
        )

    logger.info(
        "Executing Qdrant search with repository filter: %s",
        repository,
    )

    # ========================================================
    # CHECK COLLECTION
    # ========================================================

    ticket_count = qdrant_client.count(
        collection_name=COLLECTION_NAME
    ).count

    logger.info(
        "Qdrant collection contains %d tickets.",
        ticket_count,
    )

    if ticket_count == 0:

        return json.dumps(
            {
                "repository": repository,
                "matches": [],
            }
        )

    # ========================================================
    # REPOSITORY FILTER
    #
    # This is the important security/logic boundary.
    #
    # Only points whose source_repo exactly matches the
    # selected repository can be returned.
    # ========================================================

    repository_filter = Filter(
        must=[
            FieldCondition(
                key="source_repo",
                match=MatchValue(
                    value=repository
                ),
            )
        ]
    )

    # ========================================================
    # QDRANT SEARCH
    #
    # query_points() is used because your installed Qdrant
    # client does not expose the old .search() method.
    # ========================================================

    response = qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        query_filter=repository_filter,
        limit=3,
        with_payload=True,
        with_vectors=False,
    )

    points = response.points

    logger.info(
        "Qdrant returned %d matches from repository '%s'.",
        len(points),
        repository,
    )

    # ========================================================
    # FORMAT RESULTS
    # ========================================================

    matches = []

    for point in points:

        payload = point.payload or {}

        title = payload.get(
            "title",
            "Unknown ticket",
        )

        resolution = payload.get(
            "resolution",
            "No resolution available",
        )

        source_repo = payload.get(
            "source_repo",
            repository,
        )

        # ----------------------------------------------------
        # Additional safety check.
        #
        # Even though Qdrant filtered it, don't return a
        # ticket belonging to another repository.
        # ----------------------------------------------------

        if str(
            source_repo
        ).strip() != repository:

            logger.warning(
                "Qdrant returned an unexpected repository "
                "value '%s'. Expected '%s'. Skipping point.",
                source_repo,
                repository,
            )

            continue

        # ----------------------------------------------------
        # Convert cosine/distance score to percentage.
        #
        # Qdrant's score depends on the collection distance
        # configuration. We preserve the existing TicketIQ
        # interpretation used by your application.
        # ----------------------------------------------------

        try:

            score = float(
                point.score
            )

        except (
            TypeError,
            ValueError,
        ):

            score = 0.0

        score = max(
            0.0,
            min(
                100.0,
                score * 100.0,
            ),
        )

        matches.append(
            {
                "title": title,
                "resolution": resolution,
                "similarity_score": round(
                    score,
                    2,
                ),
                "source_repo": repository,
            }
        )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    return json.dumps(
        {
            "repository": repository,
            "matches": matches,
        }
    )
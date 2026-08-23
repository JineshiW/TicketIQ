"""
Agentic semantic-search workflow for TicketIQ.

Workflow:

    New Ticket
        |
        v
    Ollama
        - understand ticket
        - normalize ticket
        - identify repository
        |
        v
    SentenceTransformer
        - generate 384-dimensional embedding
        |
        v
    Qdrant
        - search ONLY selected repository
        |
        v
    Ollama
        - explain historical matches
        |
        v
    Final result
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .semantic_tools import (
    get_supported_repositories,
    ollama_ticket_tool,
    sentence_transformer_tool,
    search_repository_tickets,
)


logger = logging.getLogger("TicketIQ")


# ============================================================
# HELPERS
# ============================================================

def _parse_tool_result(
    value: Any,
) -> dict[str, Any]:
    """
    Converts a LangChain tool result into a Python dictionary.
    """

    if isinstance(
        value,
        dict,
    ):

        return value

    if isinstance(
        value,
        str,
    ):

        try:

            parsed = json.loads(
                value
            )

            if isinstance(
                parsed,
                dict,
            ):

                return parsed

        except json.JSONDecodeError:

            pass

    return {}


# ============================================================
# NORMALIZATION RESULT
# ============================================================

def _extract_normalization(
    value: Any,
) -> dict[str, Any]:

    data = _parse_tool_result(
        value
    )

    if "normalized_text" not in data:

        raise RuntimeError(
            "Ollama normalization tool did not return "
            "normalized_text."
        )

    if not data.get(
        "normalized_text"
    ):

        raise RuntimeError(
            "Ollama returned an empty normalized_text."
        )

    if "repository" not in data:

        raise RuntimeError(
            "Ollama normalization tool did not return "
            "a repository."
        )

    if not data.get(
        "repository"
    ):

        raise RuntimeError(
            "Ollama normalization tool returned an empty "
            "repository."
        )

    if "quality" not in data:

        data["quality"] = "sufficient"

    return data


# ============================================================
# EMBEDDING RESULT
# ============================================================

def _extract_embedding(
    value: Any,
) -> dict[str, Any]:

    data = _parse_tool_result(
        value
    )

    if not data:

        raise RuntimeError(
            "SentenceTransformer tool returned an empty result."
        )

    embedding = data.get(
        "embedding"
    )

    if not isinstance(
        embedding,
        list,
    ):

        raise RuntimeError(
            "SentenceTransformer tool did not return "
            "a valid embedding vector."
        )

    if not embedding:

        raise RuntimeError(
            "SentenceTransformer returned an empty embedding."
        )

    return data


# ============================================================
# SEARCH RESULT
# ============================================================

def _extract_search(
    value: Any,
) -> dict[str, Any]:

    data = _parse_tool_result(
        value
    )

    if "matches" not in data:

        raise RuntimeError(
            "Qdrant repository search did not return matches."
        )

    return data


# ============================================================
# SUMMARY RESULT
# ============================================================

def _extract_summary(
    value: Any,
) -> str:

    data = _parse_tool_result(
        value
    )

    summary = data.get(
        "summary"
    )

    if not summary:

        raise RuntimeError(
            "Ollama summary tool did not return a summary."
        )

    return str(
        summary
    )


# ============================================================
# MAIN WORKFLOW
# ============================================================

def run_semantic_search(
    ticket,
) -> dict[str, Any]:

    logger.info(
        "Starting agentic semantic search for ticket '%s'",
        ticket.id,
    )

    # ========================================================
    # STEP 1
    #
    # OLLAMA:
    # Normalize ticket + identify repository
    # ========================================================

    logger.info(
        "[Semantic Agent 1/4] "
        "Calling Ollama normalization/repository tool..."
    )

    # --------------------------------------------------------
    # Refresh repository information BEFORE calling Ollama.
    #
    # This avoids relying on a stale repository list from
    # application startup.
    # --------------------------------------------------------

    supported_repositories = (
        get_supported_repositories()
    )

    if not supported_repositories:

        raise RuntimeError(
            "No repositories were discovered in Qdrant. "
            "Make sure tickets have been imported before "
            "running semantic search."
        )

    logger.info(
        "[Semantic Agent 1/4] "
        "Available repositories: %s",
        supported_repositories,
    )

    normalization_raw = (
        ollama_ticket_tool.invoke(
            {
                "operation": "normalize",
                "title": ticket.title,
                "description": ticket.description,
            }
        )
    )

    normalization = _extract_normalization(
        normalization_raw
    )

    normalized_text = normalization[
        "normalized_text"
    ]

    repository = normalization.get(
        "repository"
    )

    if not repository:

        raise RuntimeError(
            "Ollama did not identify a repository."
        )

    repository = str(
        repository
    ).strip()

    # ========================================================
    # VALIDATE REPOSITORY
    # ========================================================

    repository_map = {
        str(repo).lower(): repo
        for repo in supported_repositories
    }

    matched_repository = repository_map.get(
        repository.lower()
    )

    if not matched_repository:

        raise RuntimeError(
            f"Ollama selected unsupported repository "
            f"'{repository}'. "
            f"Supported repositories: "
            f"{supported_repositories}"
        )

    repository = matched_repository

    logger.info(
        "[Semantic Agent 1/4] "
        "Repository identified: %s",
        repository,
    )

    logger.info(
        "[Semantic Agent 1/4] "
        "Normalized ticket: %s",
        normalized_text,
    )

    # ========================================================
    # STEP 2
    #
    # SENTENCE TRANSFORMER:
    # Generate embedding
    # ========================================================

    logger.info(
        "[Semantic Agent 2/4] "
        "Calling SentenceTransformer tool..."
    )

    embedding_raw = (
        sentence_transformer_tool.invoke(
            {
                "normalized_text": normalized_text,
            }
        )
    )

    embedding_result = _extract_embedding(
        embedding_raw
    )

    embedding = embedding_result[
        "embedding"
    ]

    logger.info(
        "[Semantic Agent 2/4] "
        "Embedding generated successfully. "
        "Dimensions: %d",
        len(embedding),
    )

    if len(embedding) != 384:

        raise RuntimeError(
            f"Expected a 384-dimensional embedding, "
            f"but SentenceTransformer returned "
            f"{len(embedding)} dimensions."
        )

    # ========================================================
    # STEP 3
    #
    # QDRANT:
    # Repository-scoped semantic search
    # ========================================================

    logger.info(
        "[Semantic Agent 3/4] "
        "Searching Qdrant ONLY in repository: %s",
        repository,
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # The actual embedding is passed directly to Qdrant.
    #
    # There is NO embedding_id.
    # --------------------------------------------------------

    search_raw = (
        search_repository_tickets.invoke(
            {
                "repository": repository,
                "embedding": json.dumps(
                    embedding
                ),
            }
        )
    )

    search_result = _extract_search(
        search_raw
    )

    matches = search_result.get(
        "matches",
        [],
    )

    logger.info(
        "[Semantic Agent 3/4] "
        "Qdrant returned %d matches from repository '%s'.",
        len(matches),
        repository,
    )

    # ========================================================
    # SAFETY CHECK
    #
    # Qdrant already applies the repository filter.
    #
    # This second Python-side check prevents an unexpected
    # repository from reaching the summary model.
    # ========================================================

    filtered_matches = []

    for match in matches:

        if not isinstance(
            match,
            dict,
        ):

            continue

        match_repository = match.get(
            "source_repo"
        )

        if match_repository:

            match_repository = str(
                match_repository
            ).strip()

            if match_repository != repository:

                logger.warning(
                    "Ignoring ticket from unexpected repository "
                    "'%s'. Expected '%s'.",
                    match_repository,
                    repository,
                )

                continue

        filtered_matches.append(
            match
        )

    search_result[
        "matches"
    ] = filtered_matches

    logger.info(
        "[Semantic Agent 3/4] "
        "After repository safety check: %d matches.",
        len(filtered_matches),
    )

    # ========================================================
    # STEP 4
    #
    # OLLAMA:
    # Explain historical matches
    # ========================================================

    logger.info(
        "[Semantic Agent 4/4] "
        "Calling Ollama for final explanation..."
    )

    search_json = json.dumps(
        search_result,
        ensure_ascii=False,
        indent=2,
    )

    summary_raw = (
        ollama_ticket_tool.invoke(
            {
                "operation": "summarize",
                "repository": repository,
                "normalized_text": normalized_text,
                "search_results": search_json,
            }
        )
    )

    summary = _extract_summary(
        summary_raw
    )

    logger.info(
        "[Semantic Agent 4/4] "
        "Final semantic-search explanation generated."
    )

    # ========================================================
    # BUILD FINAL RESPONSE
    # ========================================================

    similar_tickets = []

    for item in filtered_matches:

        similar_tickets.append(
            {
                "title": item.get(
                    "title",
                    "",
                ),
                "resolution": item.get(
                    "resolution",
                    "",
                ),
                "similarity_score": item.get(
                    "similarity_score",
                    0.0,
                ),
                "source_repo": item.get(
                    "source_repo",
                    repository,
                ),
            }
        )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    return {
        "similar_tickets": similar_tickets,

        "ai_summary": summary,

        "normalized_text": normalized_text,

        "quality": normalization.get(
            "quality",
            "sufficient",
        ),

        "source_repo": repository,
    }
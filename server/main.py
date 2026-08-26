import logging
import re
import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from pydantic import BaseModel, field_validator
import ollama
from qdrant_client.models import PointStruct
from assets.vectors.domain_terms import vector_prompt_hint
from clustering import build_cluster_response
from langgraph.types import Command
from agent.agent import pattern_review_graph
from backgroundJobs.scheduler import (
    start_scheduler,
    stop_scheduler,
    get_scheduler_status,
)
from backgroundJobs.review_store import get_all_reviews, set_review_status
from assets.shared_resources import embedder, qdrant_client, COLLECTION_NAME
from typing import Optional

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TicketIQ")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting background scheduler (recurring pattern check, every 1h)...")
    start_scheduler(qdrant_client, interval_hours=1.0)
    yield
    logger.info("Shutting down background scheduler...")
    stop_scheduler()


app = FastAPI(lifespan=lifespan)

# ============================================================
# CORS
# ============================================================

# Production Vercel frontend can be supplied through the
# environment. Multiple origins can be separated by commas.
#
# Local development remains supported through the defaults.

allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,https://client-lemon-xi-13.vercel.app",
).split(",")

allowed_origins = [
    origin.strip()
    for origin in allowed_origins
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Ticket(BaseModel):
    id: str
    title: str
    description: str
    resolution: str = ""
    source_repo: Optional[str] = None

    @field_validator("id", "title", "description")
    @classmethod
    def not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Field cannot be empty")
        return value.strip()


class SimilarTicketResult(BaseModel):
    title: str
    resolution: str
    similarity_score: float


class SimilarTicketsResponse(BaseModel):
    similar_tickets: list[SimilarTicketResult]
    ai_summary: str
    normalized_text: str
    quality: str


class BatchSimilarResult(BaseModel):
    ticket_id: str
    ticket_title: str
    result: SimilarTicketsResponse


class BatchSimilarResponse(BaseModel):
    results: list[BatchSimilarResult]


def ticket_uuid(ticket_id: str) -> str:
    """
    Qdrant requires point IDs to be integers or UUIDs, not arbitrary
    strings. This deterministically maps any string ticket ID to the
    same UUID every time, so duplicate checks and lookups still work
    correctly using your original string IDs (stored in the payload).
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, ticket_id))


def similarity_from_score(score: float) -> float:
    """
    Qdrant returns a cosine SIMILARITY score (higher = more similar,
    roughly 0 to 1), unlike ChromaDB's distance (lower = more similar).
    Converts to a 0-100 percentage for display.
    """
    return round(max(0.0, min(100.0, score * 100)), 1)


def assess_ticket_quality(title: str, description: str) -> str:
    """
    Flags tickets with vague or minimal information, so downstream
    steps (normalization, clustering) can handle them appropriately
    rather than silently treating sparse input as if it were detailed.
    """
    combined_length = len(title.strip()) + len(description.strip())

    vague_phrases = ["it's broken", "doesn't work", "not working", "help", "issue", "problem"]
    title_lower = title.lower().strip()

    if combined_length < 20:
        return "insufficient"
    elif title_lower in vague_phrases or combined_length < 50:
        return "low_detail"
    else:
        return "sufficient"


def lightweight_clean(title: str, description: str) -> str:
    """
    Cheap, rule-based cleanup for tickets that are already well-written
    (quality = 'sufficient') - skips the Ollama call entirely.
    """
    combined = f"{title}. {description}"
    combined = re.sub(r"\s+", " ", combined)
    combined = re.sub(r"[`*_#>]", "", combined)
    combined = combined.strip()
    return combined


def normalize_ticket_text(title: str, description: str, quality: str) -> str:
    """
    Routes ticket text through the appropriate cleanup path based on
    quality assessment:
    - 'insufficient': too little content to normalize meaningfully, flagged as-is
    - 'sufficient': already well-written, uses cheap rule-based cleanup only
    - 'low_detail': genuinely benefits from LLM rewriting

    Also preserves domain-specific technical vocabulary using a
    known-terms vector, so cleanup doesn't strip away terms needed
    for accurate clustering.
    """
    if quality == "insufficient":
        logger.warning("Ticket has insufficient content for normalization - using raw text as-is.")
        return f"[LOW INFO] {title}. {description}".strip()

    if quality == "sufficient":
        logger.info("Ticket quality sufficient - using lightweight rule-based cleanup (no Ollama call).")
        return lightweight_clean(title, description)

    vector_hint = vector_prompt_hint()
    vector_line = (
        f"Known domain-specific terms that must be preserved exactly if present: {vector_hint}\n"
        if vector_hint else ""
    )

    prompt = f"""Rewrite the following support ticket as a single, clean, standardized issue statement.
Remove filler words, personal phrasing, tone, and formatting noise (casual language, emoji, rhetorical questions).

CRITICAL RULES:
- PRESERVE all technical terms, component names, function names, error codes, module names,
  and domain-specific vocabulary exactly as written.
- {vector_line}- Do NOT replace specific technical nouns with generic words (e.g., do not turn
  "DRA structured allocator" into "a system component").
- Do NOT invent or guess details not present in the original text.
- If the ticket is vague or lacks enough detail to identify a specific technical issue,
  do NOT invent specifics. Instead, rewrite it as a general statement reflecting only
  what is actually stated, and prefix it with "[VAGUE]".

Respond with ONLY the rewritten statement, no explanation, no extra text.

Title: {title}
Description: {description}

Rewritten issue statement:"""

    try:
        response = ollama.chat(
            model="llama3.1:latest",
            messages=[{"role": "user", "content": prompt}]
        )
        normalized = response["message"]["content"].strip()
        logger.info(f"Normalized text: \"{normalized[:80]}...\"")
        return normalized
    except Exception as e:
        logger.warning(f"Normalization failed, falling back to raw text: {str(e)}")
        return f"{title}. {description}"


def normalize_tickets_batch(tickets_data: list[dict], quality_map: dict[str, str]) -> dict[str, str]:
    """
    Normalizes multiple tickets, but only sends tickets needing real
    LLM rewriting ('low_detail') through Ollama in a single batched call.
    """
    result = {}
    needs_llm = []

    for t in tickets_data:
        quality = quality_map.get(t["id"], "sufficient")
        if quality == "insufficient":
            result[t["id"]] = f"[LOW INFO] {t['title']}. {t['description']}".strip()
        elif quality == "sufficient":
            result[t["id"]] = lightweight_clean(t["title"], t["description"])
        else:
            needs_llm.append(t)

    logger.info(f"    Batch breakdown: {len(tickets_data) - len(needs_llm)} skipped Ollama (sufficient/insufficient), "
                f"{len(needs_llm)} sent to Ollama (low_detail)")

    if not needs_llm:
        return result

    vector_hint = vector_prompt_hint()
    ticket_block = "\n\n".join(
        f"Ticket ID {t['id']}:\nTitle: {t['title']}\nDescription: {t['description']}"
        for t in needs_llm
    )

    prompt = f"""Rewrite each of the following support tickets as a clean, standardized issue statement.
Remove filler words, personal phrasing, and formatting noise.
PRESERVE all technical terms, component names, error codes, and domain vocabulary exactly as written.
Known domain-specific terms that must be preserved if present: {vector_hint}
Do NOT invent details not present in the original text.

{ticket_block}

Respond in EXACTLY this format, one line per ticket, no extra text:
ID <id>: <rewritten statement>"""

    try:
        response = ollama.chat(model="llama3.1:latest", messages=[{"role": "user", "content": prompt}])
        content = response["message"]["content"]

        for line in content.strip().split("\n"):
            line = line.strip()
            if line.startswith("ID "):
                try:
                    id_part, text = line[3:].split(":", 1)
                    result[id_part.strip()] = text.strip()
                except ValueError:
                    continue
    except Exception as e:
        logger.warning(f"Batch normalization failed entirely: {e}")

    for t in needs_llm:
        if t["id"] not in result:
            result[t["id"]] = f"{t['title']}. {t['description']}"

    return result


@app.get("/")
def read_root():
    logger.info("GET / — health check hit")
    return {"message": "TicketIQ API is running"}


@app.post("/tickets")
def add_ticket(ticket: Ticket):
    logger.info(f"--- New request: POST /tickets (id='{ticket.id}') ---")

    try:
        point_id = ticket_uuid(ticket.id)

        logger.info(f"[1/6] Checking if ticket id '{ticket.id}' already exists in Qdrant...")
        existing = qdrant_client.retrieve(collection_name=COLLECTION_NAME, ids=[point_id])
        if existing:
            logger.warning(f"Duplicate ticket id '{ticket.id}' — rejecting request.")
            raise HTTPException(
                status_code=409,
                detail=f"A ticket with id '{ticket.id}' already exists."
            )
        logger.info("No duplicate found, proceeding.")

        logger.info(f"[2/6] Assessing ticket content quality...")
        quality = assess_ticket_quality(ticket.title, ticket.description)
        logger.info(f"Ticket quality assessed as: '{quality}'")

        logger.info(f"[3/6] Normalizing ticket text...")
        normalized_text = normalize_ticket_text(ticket.title, ticket.description, quality)

        logger.info(f"[4/6] Generating embedding via Sentence-Transformers for normalized text...")
        start = time.time()
        embedding = embedder.encode(normalized_text).tolist()
        logger.info(f"Embedding generated in {time.time() - start:.3f}s (vector length: {len(embedding)})")

        logger.info(f"[5/6] Storing ticket '{ticket.id}' in Qdrant collection '{COLLECTION_NAME}'...")
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "ticket_id": ticket.id,
                        "title": ticket.title,
                        "resolution": ticket.resolution,
                        "raw_text": f"{ticket.title}. {ticket.description}",
                        "normalized_text": normalized_text,
                        "quality": quality,
                        "source_repo": ticket.source_repo,
                    },
                )
            ],
        )
        new_count = qdrant_client.count(collection_name=COLLECTION_NAME).count
        logger.info(f"Ticket stored. New total ticket count: {new_count}")

        logger.info(f"[6/6] Done — ticket '{ticket.id}' added successfully.")
        return {
            "message": f"Ticket {ticket.id} added successfully",
            "normalized_text": normalized_text,
            "quality": quality
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add ticket '{ticket.id}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to add ticket: {str(e)}")


@app.post("/tickets/batch")
def add_tickets_batch(tickets: list[Ticket]):
    """
    Adds multiple tickets in one request. Only tickets needing genuine
    LLM rewriting ('low_detail') go through a single batched Ollama call;
    well-written ('sufficient') tickets use cheap rule-based cleanup instead.
    """
    logger.info(f"--- New request: POST /tickets/batch ({len(tickets)} tickets) ---")

    new_tickets = []
    skipped = []
    for t in tickets:
        existing = qdrant_client.retrieve(collection_name=COLLECTION_NAME, ids=[ticket_uuid(t.id)])
        if existing:
            skipped.append(t.id)
        else:
            new_tickets.append(t)

    logger.info(f"[1/4] {len(new_tickets)} new tickets, {len(skipped)} already exist (skipped)")

    if not new_tickets:
        return {"added": 0, "skipped": skipped}

    logger.info(f"[2/4] Assessing quality for {len(new_tickets)} tickets...")
    quality_map = {
        t.id: assess_ticket_quality(t.title, t.description) for t in new_tickets
    }

    logger.info(f"[3/4] Normalizing batch (only low-detail tickets go through Ollama)...")
    tickets_data = [{"id": t.id, "title": t.title, "description": t.description} for t in new_tickets]
    normalized_map = normalize_tickets_batch(tickets_data, quality_map)

    logger.info(f"[4/4] Embedding and storing {len(new_tickets)} tickets...")
    points = []
    for t in new_tickets:
        normalized_text = normalized_map.get(t.id, f"{t.title}. {t.description}")
        embedding = embedder.encode(normalized_text).tolist()
        points.append(
            PointStruct(
                id=ticket_uuid(t.id),
                vector=embedding,
                payload={
                    "ticket_id": t.id,
                    "title": t.title,
                    "resolution": t.resolution,
                    "raw_text": f"{t.title}. {t.description}",
                    "normalized_text": normalized_text,
                    "quality": quality_map.get(t.id, "sufficient"),
                    "source_repo": t.source_repo,
                },
            )
        )

    qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
    new_count = qdrant_client.count(collection_name=COLLECTION_NAME).count
    logger.info(f"Batch complete. Added: {len(points)}, skipped: {len(skipped)}. Total tickets: {new_count}")
    return {"added": len(points), "skipped": skipped}


@app.post(
    "/tickets/similar",
    response_model=SimilarTicketsResponse,
)
def find_similar(ticket: Ticket):

    """
    Agentic semantic-search workflow.

    The frontend endpoint remains unchanged.

    Internally:

        ticket
          ↓
        semantic agent
          ↓
        Ollama normalization
          ↓
        Sentence Transformer
          ↓
        repository identification
          ↓
        repository-filtered Qdrant search
          ↓
        Ollama explanation
          ↓
        existing API response
    """

    logger.info(
        f"--- New request: POST /tickets/similar "
        f"(id='{ticket.id}', title='{ticket.title}') ---"
    )

    try:

        # Lazy import prevents a circular import between main.py
        # and the semantic agent/tool modules.
        from agent.semantic_agent import (
            run_semantic_search
        )

        result = run_semantic_search(
            ticket
        )

        logger.info(
            "Semantic agent complete: "
            f"{len(result.get('similar_tickets', []))} "
            "repository-scoped matches returned."
        )

        return SimilarTicketsResponse(
            **result
        )

    except Exception as e:

        logger.exception(
            "Agentic semantic search failed"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Semantic search failed: {str(e)}",
        )


@app.post("/tickets/similar/batch", response_model=BatchSimilarResponse)
def find_similar_batch(tickets: list[Ticket]):
    """
    Accepts multiple new tickets in one request. Each ticket is only
    ever compared against the existing stored database, never against
    other tickets in this same batch.
    """
    logger.info(f"--- New request: POST /tickets/similar/batch ({len(tickets)} tickets) ---")

    batch_results = []
    for ticket in tickets:
        single_result = find_similar(ticket)
        batch_results.append(
            BatchSimilarResult(
                ticket_id=ticket.id,
                ticket_title=ticket.title,
                result=single_result
            )
        )

    logger.info(f"Batch similarity check complete for {len(tickets)} tickets.")
    return BatchSimilarResponse(results=batch_results)


@app.get("/clusters")
def get_clusters():
    """
    Returns the current recurring-pattern view.

    Clustering itself may be recomputed on every request, but
    build_cluster_response() reconciles the newly discovered clusters
    with the persistent review store.

    Therefore existing pattern labels, summaries, signatures and
    review statuses remain stable across soft refreshes and hard
    browser refreshes.
    """

    logger.info(
        "--- New request: GET /clusters ---"
    )

    result = build_cluster_response(
        qdrant_client
    )

    logger.info(
        "Clustering/reconciliation complete. "
        "Best algorithm: %s, %d clusters returned.",
        result.get(
            "best_algorithm"
        ),
        len(
            result.get(
                "clusters",
                [],
            )
        ),
    )

    return result


@app.get("/clusters/reviews")
def list_pending_reviews():
    """
    Returns all recurring patterns tracked so far by the background
    scheduler, with their current status (pending/approved/rejected).
    """
    logger.info("--- New request: GET /clusters/reviews ---")
    return get_all_reviews()

@app.get("/clusters/schedule")
def get_cluster_schedule():
    """
    Returns metadata about the automatic recurring-pattern
    scheduler.

    This endpoint is intentionally read-only.

    It does NOT trigger clustering.
    """

    logger.info(
        "--- New request: GET /clusters/schedule ---"
    )

    return get_scheduler_status()


@app.post("/clusters/reviews/decide")
def decide_review(signature: str, decision: str):
    """Approve/reject a recurring pattern.

    The signature is a query parameter because repository names contain
    '/' (for example 'kubernetes/kubernetes'). A normal path parameter
    can therefore be split into multiple URL path segments and produce
    a 404 even though the signature exists.
    """
    logger.info(
        "--- New request: POST /clusters/reviews/decide "
        "(decision='%s', signature='%s...') ---",
        decision,
        signature[:30],
    )
    try:
        success = set_review_status(signature, decision)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not success:
        raise HTTPException(status_code=404, detail="Cluster signature not found")

    return {"signature": signature, "status": decision}


@app.post("/agent/check-patterns")
def trigger_pattern_check():
    """
    Manual/ad-hoc agentic trigger. Runs clustering via the LangGraph
    agent, detects patterns, and PAUSES - returns findings plus a
    thread_id needed to resume.
    """
    logger.info("--- New request: POST /agent/check-patterns ---")
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    result = pattern_review_graph.invoke({"messages": []}, config=config)

    if "__interrupt__" not in result:
        logger.info("No patterns requiring review were found.")
        return {"message": "No patterns requiring review were found.", "thread_id": None}

    interrupt_data = result["__interrupt__"][0].value
    logger.info(f"Pattern check paused, awaiting human decision. thread_id={thread_id}")

    return {
        "thread_id": thread_id,
        "findings": interrupt_data["findings"],
        "question": interrupt_data["question"]
    }


@app.post("/agent/resume/{thread_id}")
def resume_pattern_check(thread_id: str, decision: str):
    """
    Human-in-the-loop decision point. Submit your real decision here
    to resume the paused graph.
    """
    logger.info(f"--- New request: POST /agent/resume/{thread_id} (decision='{decision}') ---")
    config = {"configurable": {"thread_id": thread_id}}

    final_result = pattern_review_graph.invoke(Command(resume=decision), config=config)
    final_message = final_result["messages"][-1].content

    logger.info(f"Pattern review resumed and completed for thread_id={thread_id}")
    return {"thread_id": thread_id, "final_result": final_message}
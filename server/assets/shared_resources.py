import logging
import os
from pathlib import Path

from sentence_transformers import SentenceTransformer

from qdrant_client import QdrantClient

from qdrant_client.models import (
    Distance,
    VectorParams,
    PayloadSchemaType,
)


logger = logging.getLogger("TicketIQ")


# ============================================================
# SENTENCE TRANSFORMER
# ============================================================

logger.info(
    "Loading Sentence-Transformers model "
    "'all-MiniLM-L6-v2'..."
)

embedder = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

logger.info(
    "Embedding model loaded."
)


# ============================================================
# QDRANT
# ============================================================

# Resolve the project/server directory from this file's location.
#
# shared_resources.py
#     ↓
# assets/
#     ↓
# server/
#
# Therefore parents[1] = server/
SERVER_DIR = Path(__file__).resolve().parents[1]

# Allow production to override the location if necessary,
# while keeping the existing local qdrant_db directory as
# the default.
QDRANT_PATH = Path(
    os.getenv(
        "QDRANT_PATH",
        str(SERVER_DIR / "qdrant_db"),
    )
).expanduser().resolve()


logger.info(
    "Connecting to Qdrant "
    f"(local mode, path='{QDRANT_PATH}')..."
)


qdrant_client = QdrantClient(
    path=str(QDRANT_PATH),
    force_disable_check_same_thread=True,
)


COLLECTION_NAME = "tickets"

VECTOR_SIZE = (
    embedder
    .get_sentence_embedding_dimension()
)


# ============================================================
# COLLECTION INITIALISATION
# ============================================================

if not qdrant_client.collection_exists(
    COLLECTION_NAME
):

    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE,
        ),
    )

    logger.info(
        f"Created new Qdrant collection "
        f"'{COLLECTION_NAME}'."
    )


# ============================================================
# REPOSITORY FILTER INDEX
# ============================================================

try:

    qdrant_client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="source_repo",
        field_schema=PayloadSchemaType.KEYWORD,
    )

except Exception as exc:

    logger.info(
        "source_repo payload index already "
        f"exists or could not be created: {exc}"
    )


# ============================================================
# STARTUP INFORMATION
# ============================================================

ticket_count = qdrant_client.count(
    collection_name=COLLECTION_NAME
).count


logger.info(
    "Qdrant ready. Current ticket count: "
    f"{ticket_count}"
)
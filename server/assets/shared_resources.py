import logging

from sentence_transformers import (
    SentenceTransformer,
)

from qdrant_client import (
    QdrantClient,
)

from qdrant_client.models import (
    Distance,
    VectorParams,
    PayloadSchemaType,
)


logger = logging.getLogger(
    "TicketIQ"
)


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


logger.info(
    "Connecting to Qdrant "
    "(local mode, path='./qdrant_db')..."
)

qdrant_client = QdrantClient(
    path="./qdrant_db",
    force_disable_check_same_thread=True,
)


COLLECTION_NAME = "tickets"

VECTOR_SIZE = (
    embedder
    .get_sentence_embedding_dimension()
)


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


# Repository-scoped semantic search uses
# this payload field for filtering.
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


ticket_count = qdrant_client.count(
    collection_name=COLLECTION_NAME
).count

logger.info(
    f"Qdrant ready. Current ticket count: "
    f"{ticket_count}"
)
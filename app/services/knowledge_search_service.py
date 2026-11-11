
from sqlalchemy import text, bindparam
from sqlalchemy.orm import Session
from pgvector.sqlalchemy import Vector
from uuid import UUID

from app.services.embedding_service import generate_embedding


def search_knowledge(
    db: Session,
    question: str,
    product_id: UUID,
    limit: int = 5,
    min_similarity: float = 0.50,
) -> list[dict]:

    # 1. Convert the question into a 768-dimensional embedding
    query_embedding = generate_embedding(question)

    # 2. Call our PostgreSQL similarity-search function
    query = text("""
        SELECT
            chunks.*,
            documents.title AS document_title,
            documents.file_name AS document_file_name
        FROM public.search_knowledge_chunks(
            :query_embedding,
            :match_product_id,
            :match_count
        ) AS chunks
        JOIN public.ayabot_knowledge_documents AS documents
            ON documents.id = chunks.document_id
        AND documents.product_id = :match_product_id
        WHERE chunks.similarity >= :min_similarity
    """).bindparams(
        bindparam("query_embedding", type_=Vector(768))
    )

    result = db.execute(
        query,
        {
            "min_similarity": min_similarity,
            "query_embedding": query_embedding,
            "match_product_id": product_id,
            "match_count": limit,
        },
    )

    rows = result.mappings().all()

    if rows:
        print("Knowledge result fields:", list(rows[0].keys()))

    return [dict(row) for row in rows]

    # 3. Return matching chunks
    # return [dict(row) for row in result.mappings().all()]

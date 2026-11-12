
from sqlalchemy import text, bindparam
from sqlalchemy.orm import Session
from pgvector.sqlalchemy import Vector
from uuid import UUID
import re

from app.services.embedding_service import generate_embedding



def remove_redundant_chunks(
    chunks: list[dict],
    overlap_threshold: float = 0.90,
) -> list[dict]:
    """
    Remove chunks that are almost entirely duplicated.

    Keeps the higher-similarity chunk when substantial
    textual duplication is detected.
    """

    def normalize(content: str) -> set[str]:
        content = content.lower()
        content = re.sub(r"\s+", " ", content)
        return set(re.findall(r"\b\w+\b", content))

    selected: list[dict] = []
    selected_words: list[set[str]] = []

    for chunk in chunks:
        words = normalize(chunk.get("content", ""))

        if not words:
            continue

        duplicate = False

        for existing_words in selected_words:
            overlap = len(words & existing_words) / len(words | existing_words)

            if overlap >= overlap_threshold:
                duplicate = True
                break

        if not duplicate:
            selected.append(chunk)
            selected_words.append(words)

    return selected



def search_knowledge(
    db: Session,
    question: str,
    product_id: UUID,
    limit: int = 10,
    candidate_limit: int = 20,
    min_similarity: float = 0.50,
) -> list[dict]:

    # 1. Generate question embedding
    query_embedding = generate_embedding(question)

    # 2. Retrieve candidate chunks from PostgreSQL
    query = text("""
        SELECT
            chunks.*,
            documents.title AS document_title,
            documents.file_name AS document_file_name
        FROM public.search_knowledge_chunks(
            :query_embedding,
            :match_product_id,
            :candidate_count
        ) AS chunks
        JOIN public.ayabot_knowledge_documents AS documents
            ON documents.id = chunks.document_id
           AND documents.product_id = :match_product_id
        ORDER BY chunks.similarity DESC
    """).bindparams(
        bindparam("query_embedding", type_=Vector(768))
    )

    result = db.execute(
        query,
        {
            "query_embedding": query_embedding,
            "match_product_id": product_id,
            "candidate_count": candidate_limit,
        },
    )

    rows = [dict(row) for row in result.mappings().all()]

    filtered_rows = [
        row for row in rows
        if row["similarity"] >= min_similarity
    ]

    deduplicated_rows = remove_redundant_chunks(filtered_rows)

    final_results = deduplicated_rows[:limit]

    print(
        f"[RAG] Candidates retrieved: {len(rows)}, "
        f"Above threshold: {len(filtered_rows)}, "
        f"After deduplication: {len(deduplicated_rows)}, "
        f"Final results: {len(final_results)}"
    )
    return final_results

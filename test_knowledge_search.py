
from uuid import UUID

from app.db.session import SessionLocal
from app.services.knowledge_search_service import search_knowledge


PRODUCT_ID = UUID("2954c1bd-466c-403e-af6d-3c7e6f419d93")

QUESTION = "What is the best recipe for making chocolate cake?"

db = SessionLocal()

try:
    results = search_knowledge(
        db=db,
        question=QUESTION,
        product_id=PRODUCT_ID,
        limit=5,
    )

    print(f"\nQuestion: {QUESTION}")
    print(f"Retrieved chunks: {len(results)}\n")

    for index, result in enumerate(results, start=1):
        print(f"--- Result {index} ---")
        print(f"Chunk ID: {result['chunk_id']}")
        print(f"Similarity: {result['similarity']:.4f}")
        print(f"Content:\n{result['content']}\n")

finally:
    db.close()

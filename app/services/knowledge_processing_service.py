
from datetime import datetime, timezone
from uuid import UUID

from app.db.session import SessionLocal
from app.models.knowledge_document import AyabotKnowledgeDocument
from app.models.knowledge_chunk import AyabotKnowledgeChunk

from app.services.storage_service import download_knowledge_file
from app.services.document_extractor import extract_text
from app.services.text_chunker import split_text
from app.services.embedding_service import generate_embedding


def process_knowledge_document(document_id: UUID) -> None:
    db = SessionLocal()

    print(f"\n{'=' * 55}")
    print(f"[AYABOT] Processing document: {document_id}")

    try:
        # 1. Load document
        print("[1/7] Loading document from database...")

        document = db.get(AyabotKnowledgeDocument, document_id)

        if not document:
            print("[ERROR] Document not found")
            return

        print(f"[SUCCESS] Document: {document.title}")
        print(f"[INFO] File: {document.file_name}")

        # 2. Update status
        print("[2/7] Updating status to processing...")

        document.status = "processing"
        document.error_message = None
        document.updated_at = datetime.now(timezone.utc)
        db.commit()

        print("[SUCCESS] Status updated")

        # 3. Download file
        print("[3/7] Downloading file from Supabase Storage...")

        file_content = download_knowledge_file(document.file_path)

        print(f"[SUCCESS] Downloaded {len(file_content)} bytes")

        # 4. Extract text
        print("[4/7] Extracting document text...")

        extracted_text = extract_text(
            file_content=file_content,
            file_name=document.file_name,
        )

        print(f"[SUCCESS] Extracted {len(extracted_text)} characters")
        print(f"[INFO] Preview: {extracted_text[:200]!r}")

        # 5. Split text
        print("[5/7] Splitting text into chunks...")

        chunks = split_text(extracted_text)

        if not chunks:
            raise ValueError("No text chunks generated")

        print(f"[SUCCESS] Generated {len(chunks)} chunks")

        # 6. Generate embeddings
        print("[6/7] Generating Gemini embeddings...")

        chunk_records = []

        for index, chunk_content in enumerate(chunks):
            print(
                f"[INFO] Embedding chunk {index + 1}/{len(chunks)}..."
            )

            embedding = generate_embedding(chunk_content)

            print(
                f"[SUCCESS] Chunk {index + 1}: "
                f"{len(embedding)} dimensions"
            )

            chunk_records.append(
                AyabotKnowledgeChunk(
                    document_id=document.id,
                    product_id=document.product_id,
                    chunk_index=index,
                    content=chunk_content,
                    embedding=embedding,
                )
            )

        # 7. Save chunks and complete
        print("[7/7] Saving chunks to PostgreSQL...")

        db.query(AyabotKnowledgeChunk).filter(
            AyabotKnowledgeChunk.document_id == document.id
        ).delete(synchronize_session=False)

        db.add_all(chunk_records)

        document.status = "completed"
        document.error_message = None
        document.updated_at = datetime.now(timezone.utc)

        db.commit()

        print(f"[SUCCESS] Saved {len(chunk_records)} chunks")
        print("[SUCCESS] Document processing completed!")

    except Exception as exc:
        db.rollback()

        print(f"\n[FAILED] Document processing failed!")
        print(f"[ERROR] {type(exc).__name__}: {exc}")

        try:
            document = db.get(
                AyabotKnowledgeDocument,
                document_id,
            )

            if document:
                document.status = "failed"
                document.error_message = str(exc)[:2000]
                document.updated_at = datetime.now(timezone.utc)
                db.commit()

                print("[INFO] Document status updated to failed")

        except Exception as status_exc:
            db.rollback()
            print(f"[ERROR] Could not update failure status: {status_exc}")

    finally:
        db.close()
        print(f"[AYABOT] Processing finished: {document_id}")
        print(f"{'=' * 55}\n")

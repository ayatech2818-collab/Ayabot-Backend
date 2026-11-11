from pathlib import Path
from uuid import UUID, uuid4
from fastapi import BackgroundTasks
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from datetime import datetime, timezone
from app.services.gemini_text_service import generate_knowledge_answer

from uuid import uuid4

from sqlalchemy import select, func, delete

from app.models.knowledge_chunk import AyabotKnowledgeChunk

from pydantic import BaseModel, Field

from app.services.knowledge_processing_service import (
    process_knowledge_document,
)
from app.services.knowledge_search_service import search_knowledge

from app.api.dependencies import get_current_admin, get_db, get_current_product

from app.models.product import AyabotProduct
from app.models.knowledge_document import AyabotKnowledgeDocument
from app.schemas.knowledge_document import KnowledgeDocumentResponse
from app.services.storage_service import (
    upload_knowledge_file,
    delete_knowledge_file,
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Management"])

class KnowledgeSearchRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)


class KnowledgeSearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    document_file_name: str
    content: str
    similarity: float


class KnowledgeSearchResponse(BaseModel):
    success: bool
    results: list[KnowledgeSearchResult]

class KnowledgeAnswerResponse(BaseModel):
    success: bool
    answer: str
    sources: list[KnowledgeSearchResult]

class KnowledgeDocumentDetailResponse(KnowledgeDocumentResponse):
    total_chunks: int
    embedded_chunks: int

MAX_FILE_SIZE = 10 * 1024 * 1024

ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}


@router.post(
    "/documents",
    response_model=KnowledgeDocumentResponse,
    status_code=201,
)
async def upload_knowledge_document(
    background_tasks: BackgroundTasks,
    product_id: UUID = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    # 1. Validate product
    product = db.get(AyabotProduct, product_id)

    if not product or not product.is_active:
        raise HTTPException(
            status_code=404,
            detail="Active product not found",
        )

    # 2. Validate filename and file type
    original_filename = Path(file.filename or "").name
    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, DOCX and TXT files are supported",
        )

    mime_type = ALLOWED_TYPES[extension]

    # 3. Read with a strict size limit
    content = await file.read(MAX_FILE_SIZE + 1)

    if not content:
        raise HTTPException(status_code=400, detail="File is empty")

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Maximum file size is 10 MB",
        )

    # 4. Generate a safe storage path
    document_id = uuid4()

    storage_path = (
        f"{product.id}/{document_id}/original{extension}"
    )

    # 5. Upload original file
    try:
        upload_knowledge_file(
            file_path=storage_path,
            file_content=content,
            content_type=mime_type,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Failed to upload document to storage",
        ) from exc

    # 6. Save document metadata
    try:
        document = AyabotKnowledgeDocument(
            id=document_id,
            product_id=product.id,
            title=title.strip(),
            file_name=original_filename,
            file_path=storage_path,
            mime_type=mime_type,
            file_size=len(content),
            status="pending",
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        background_tasks.add_task(
            process_knowledge_document,
            document.id,
        )

        return document

    except Exception as exc:
        db.rollback()

        try:
            delete_knowledge_file(storage_path)
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail="Failed to save document information",
        ) from exc



@router.put("/documents/{document_id}/replace", response_model=KnowledgeDocumentResponse)
async def replace_knowledge_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    document = db.get(AyabotKnowledgeDocument, document_id)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Knowledge document not found",
        )

    if document.status in ("pending", "processing"):
        raise HTTPException(
            status_code=409,
            detail="Cannot replace a document while processing",
        )

    if document.previous_file_path:
        raise HTTPException(
            status_code=409,
            detail="A previous replacement file still needs cleanup. Resolve it before replacing again.",
        )

    original_filename = Path(file.filename or "").name
    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, DOCX and TXT files are supported",
        )

    mime_type = ALLOWED_TYPES[extension]

    content = await file.read(MAX_FILE_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="File is empty",
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Maximum file size is 10 MB",
        )

    replacement_id = uuid4()
    storage_path = (
        f"{document.product_id}/{document.id}/"
        f"replacement_{replacement_id}{extension}"
    )

    try:
        upload_knowledge_file(
            file_path=storage_path,
            file_content=content,
            content_type=mime_type,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Failed to upload replacement file",
        ) from exc

    old_file_path = document.file_path

    try:
        document.previous_file_path = old_file_path
        document.file_path = storage_path
        document.file_name = original_filename
        document.mime_type = mime_type
        document.file_size = len(content)
        document.status = "pending"
        document.error_message = None
        document.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(document)

    except Exception as exc:
        db.rollback()

        print(f"[REPLACE ERROR] {type(exc).__name__}: {exc}")

        try:
            delete_knowledge_file(storage_path)
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail="Failed to update document information",
        ) from exc

    background_tasks.add_task(
        process_knowledge_document,
        document.id,
    )

    return document



@router.get(
    "/documents/{document_id}",
    response_model=KnowledgeDocumentDetailResponse,
)
def get_knowledge_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    document = db.get(AyabotKnowledgeDocument, document_id)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Knowledge document not found",
        )

    chunk_counts = db.execute(
        select(
            func.count(AyabotKnowledgeChunk.id),
            func.count(AyabotKnowledgeChunk.embedding),
        ).where(
            AyabotKnowledgeChunk.document_id == document_id
        )
    ).one()

    return {
        "id": document.id,
        "product_id": document.product_id,
        "title": document.title,
        "file_name": document.file_name,
        "file_path": document.file_path,
        "mime_type": document.mime_type,
        "file_size": document.file_size,
        "status": document.status,
        "error_message": document.error_message,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "total_chunks": chunk_counts[0],
        "embedded_chunks": chunk_counts[1],
    }

@router.get("/documents", response_model=list[KnowledgeDocumentResponse])
def list_knowledge_documents(
    product_id: UUID | None = None,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    query = select(AyabotKnowledgeDocument)

    if product_id:
        query = query.where(
            AyabotKnowledgeDocument.product_id == product_id
        )

    query = query.order_by(
        AyabotKnowledgeDocument.created_at.desc()
    )

    documents = db.execute(query).scalars().all()

    return documents



@router.post(
    "/documents/{document_id}/retry",
    response_model=KnowledgeDocumentResponse,
)
def retry_knowledge_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    document = db.get(AyabotKnowledgeDocument, document_id)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Knowledge document not found",
        )

    if document.status not in ("failed", "pending"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry document with status '{document.status}'",
        )

    document.status = "pending"
    document.error_message = None

    db.commit()
    db.refresh(document)

    background_tasks.add_task(
        process_knowledge_document,
        document.id,
    )

    return document


@router.delete("/documents/{document_id}")
def delete_knowledge_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    document = db.get(AyabotKnowledgeDocument, document_id)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Knowledge document not found",
        )

    try:
        delete_knowledge_file(document.file_path)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Failed to delete document from storage",
        ) from exc

    try:
        db.delete(document)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to delete document from database",
        ) from exc

    return {
        "success": True,
        "message": "Knowledge document deleted successfully",
        "document_id": str(document_id),
    }


@router.post(
    "/search",
    response_model=KnowledgeSearchResponse,
)
def search_product_knowledge(
    payload: KnowledgeSearchRequest,
    db: Session = Depends(get_db),
    product=Depends(get_current_product),
):
    results = search_knowledge(
        db=db,
        question=payload.question,
        product_id=product.product.id,
        limit=10,
        min_similarity=0.50,
    )

    return {
        "success": True,
        "results": [
            {
                "chunk_id": result["chunk_id"],
                "document_id": result["document_id"],
                "document_title": result["document_title"],
                "document_file_name": result["document_file_name"],
                "content": result["content"],
                "similarity": result["similarity"],
            }
            for result in results
        ],
    }

@router.post(
    "/answer",
    response_model=KnowledgeAnswerResponse,
)
def answer_product_question(
    payload: KnowledgeSearchRequest,
    db: Session = Depends(get_db),
    product=Depends(get_current_product),
):
    # 1. Retrieve product-specific knowledge
    results = search_knowledge(
        db=db,
        question=payload.question,
        product_id=product.product.id,
        limit=10,
        min_similarity=0.50,
    )

    # 2. Generate an AI answer using Gemini
    answer = generate_knowledge_answer(
        question=payload.question,
        knowledge_chunks=results,
    )

    # 3. Return answer and retrieved sources
    return {
        "success": True,
        "answer": answer,
                "sources": [
            {
                "chunk_id": result["chunk_id"],
                "document_id": result["document_id"],
                "document_title": result["document_title"],
                "document_file_name": result["document_file_name"],
                "content": result["content"],
                "similarity": result["similarity"],
            }
            for result in results
        ],
    }
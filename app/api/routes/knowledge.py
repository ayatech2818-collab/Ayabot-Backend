from pathlib import Path
from uuid import UUID, uuid4
from fastapi import BackgroundTasks
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.services.knowledge_processing_service import (
    process_knowledge_document,
)

from app.api.dependencies import get_current_admin, get_db
from app.core.supabase import get_supabase_client
from app.models.product import AyabotProduct
from app.models.knowledge_document import AyabotKnowledgeDocument
from app.schemas.knowledge_document import KnowledgeDocumentResponse
from app.services.storage_service import (
    upload_knowledge_file,
    delete_knowledge_file,
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Management"])

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
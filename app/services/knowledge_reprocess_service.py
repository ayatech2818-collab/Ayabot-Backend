
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.knowledge_document import AyabotKnowledgeDocument


def prepare_document_for_reprocessing(
    db: Session,
    document_id: UUID,
) -> AyabotKnowledgeDocument:

    document = (
        db.query(AyabotKnowledgeDocument)
        .filter(AyabotKnowledgeDocument.id == document_id)
        .with_for_update()
        .first()
    )

    if not document:
        raise LookupError("Knowledge document not found")

    if document.status in ("pending", "processing"):
        raise RuntimeError(
            f"Cannot reprocess document with status '{document.status}'"
        )

    try:
        document.status = "pending"
        document.error_message = None
        document.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(document)

        return document

    except Exception:
        db.rollback()
        raise

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scope import AyabotScope


DEFAULT_SCOPES = [
    {
        "name": "chat:access",
        "description": "Access chatbot functionality",
    },
    {
        "name": "enquiries:create",
        "description": "Create admission enquiries",
    },
    {
        "name": "knowledge:read",
        "description": "Read knowledge-base information",
    },
    {
        "name": "courses:read",
        "description": "Read course information",
    },
]


def seed_default_scopes(db: Session):
    created_scopes = []

    for scope_data in DEFAULT_SCOPES:
        existing_scope = db.scalar(
            select(AyabotScope).where(
                AyabotScope.name == scope_data["name"]
            )
        )

        if existing_scope is None:
            scope = AyabotScope(**scope_data)
            db.add(scope)
            created_scopes.append(scope)

    if created_scopes:
        db.commit()

        for scope in created_scopes:
            db.refresh(scope)

    return created_scopes
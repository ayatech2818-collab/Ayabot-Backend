from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin
from app.db.dependencies import get_db
from app.models.admin import AyabotAdmin
from app.schemas.product_credential import (
    CredentialCreate,
    CredentialResponse,
    CredentialCreatedResponse,
)
from app.services.product_credential_service import (
    create_product_credential,
    get_product_credentials,
    revoke_product_credential,
)

router = APIRouter(
    prefix="/products/{product_id}/credentials",
    tags=["Product Credentials"],
)


@router.post(
    "",
    response_model=CredentialCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_credential(
    product_id: UUID,
    credential_data: CredentialCreate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AyabotAdmin, Depends(get_current_admin)],
):
    credential, api_key = create_product_credential(
        db=db,
        product_id=product_id,
        credential_data=credential_data,
    )

    return {
        **CredentialResponse.model_validate(credential).model_dump(),
        "api_key": api_key,
    }


@router.get(
    "",
    response_model=list[CredentialResponse],
)
def list_credentials(
    product_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AyabotAdmin, Depends(get_current_admin)],
    include_inactive: bool = Query(default=False),
):
    return get_product_credentials(
        db=db,
        product_id=product_id,
        include_inactive=include_inactive,
    )


@router.delete(
    "/{credential_id}",
    response_model=CredentialResponse,
)
def revoke_credential(
    product_id: UUID,
    credential_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AyabotAdmin, Depends(get_current_admin)],
):
    return revoke_product_credential(
        db=db,
        product_id=product_id,
        credential_id=credential_id,
    )
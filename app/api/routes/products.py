
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin
from app.db.dependencies import get_db
from app.models.admin import AyabotAdmin
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.product_service import create_product, get_products, get_product_by_id, update_product, deactivate_product, restore_product

from fastapi import APIRouter, Depends, Query, status

from uuid import UUID


router = APIRouter(
    prefix="/products",
    tags=["Products"],
)


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_product(
    product_data: ProductCreate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AyabotAdmin, Depends(get_current_admin)],
):
    return create_product(db, product_data)



@router.get(
    "",
    response_model=list[ProductResponse],
)
def list_products(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AyabotAdmin, Depends(get_current_admin)],
    include_inactive: bool = False,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
):
    return get_products(
        db=db,
        include_inactive=include_inactive,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
)
def retrieve_product(
    product_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AyabotAdmin, Depends(get_current_admin)],
):
    return get_product_by_id(
        db=db,
        product_id=product_id,
    )


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
)
def modify_product(
    product_id: UUID,
    product_data: ProductUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AyabotAdmin, Depends(get_current_admin)],
):
    return update_product(
        db=db,
        product_id=product_id,
        product_data=product_data,
    )



@router.delete(
    "/{product_id}",
    response_model=ProductResponse,
)
def delete_product(
    product_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AyabotAdmin, Depends(get_current_admin)],
):
    return deactivate_product(
        db=db,
        product_id=product_id,
    )


@router.patch(
    "/{product_id}/restore",
    response_model=ProductResponse,
)
def restore_existing_product(
    product_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AyabotAdmin, Depends(get_current_admin)],
):
    return restore_product(
        db=db,
        product_id=product_id,
    )

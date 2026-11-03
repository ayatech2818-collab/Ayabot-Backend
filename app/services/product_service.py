
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.product import AyabotProduct
from app.schemas.product import ProductCreate, ProductUpdate

from sqlalchemy import select

from uuid import UUID


def create_product(
    db: Session,
    product_data: ProductCreate,
) -> AyabotProduct:

    # Check whether the slug already exists
    existing_product = db.scalar(
        select(AyabotProduct).where(
            AyabotProduct.slug == product_data.slug
        )
    )

    if existing_product:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this slug already exists",
        )

    # Create product instance
    product = AyabotProduct(
        name=product_data.name,
        slug=product_data.slug,
        description=product_data.description,
    )

    try:
        db.add(product)
        db.commit()
        db.refresh(product)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this slug already exists",
        ) from None

    except Exception:
        db.rollback()
        raise

    return product



def get_products(
    db: Session,
    include_inactive: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> list[AyabotProduct]:

    query = select(AyabotProduct)

    if not include_inactive:
        query = query.where(
            AyabotProduct.is_active.is_(True)
        )

    query = (
        query
        .order_by(AyabotProduct.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    return list(db.scalars(query).all())


def get_product_by_id(
    db: Session,
    product_id: UUID,
) -> AyabotProduct:

    product = db.get(AyabotProduct, product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return product


def update_product(
    db: Session,
    product_id: UUID,
    product_data: ProductUpdate,
) -> AyabotProduct:

    product = get_product_by_id(db, product_id)

    update_data = product_data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    # Check slug uniqueness if slug is being changed
    if "slug" in update_data:
        existing_product = db.scalar(
            select(AyabotProduct).where(
                AyabotProduct.slug == update_data["slug"],
                AyabotProduct.id != product_id,
            )
        )

        if existing_product:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A product with this slug already exists",
            )

    for field, value in update_data.items():
        setattr(product, field, value)

    try:
        db.commit()
        db.refresh(product)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this slug already exists",
        ) from None

    except Exception:
        db.rollback()
        raise

    return product



def deactivate_product(
    db: Session,
    product_id: UUID,
) -> AyabotProduct:

    product = get_product_by_id(db, product_id)

    if not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product is already inactive",
        )

    try:
        product.is_active = False

        db.commit()
        db.refresh(product)

    except Exception:
        db.rollback()
        raise

    return product


def restore_product(
    db: Session,
    product_id: UUID,
) -> AyabotProduct:

    product = get_product_by_id(db, product_id)

    if product.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product is already active",
        )

    try:
        product.is_active = True

        db.commit()
        db.refresh(product)

    except Exception:
        db.rollback()
        raise

    return product

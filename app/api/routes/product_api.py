from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    ProductAuthContext,
    get_current_product,
)
from app.schemas.product import ProductResponse


router = APIRouter(
    prefix="/product",
    tags=["Product API"],
)


@router.get("/me", response_model=ProductResponse)
def get_authenticated_product(
    ctx: Annotated[
        ProductAuthContext,
        Depends(get_current_product),
    ],
):
    return ctx.product
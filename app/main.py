
from fastapi import FastAPI

from app.api.routes.auth import router as auth_router

from app.core.config import get_settings

from app.api.routes.products import router as products_router

from app.api.routes.product_credentials import router as product_credentials_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Internal multi-product AI assistant platform for Ayadi",
    version="0.1.0",
    debug=settings.debug,
)

app.include_router(
    auth_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    products_router,
    prefix=settings.api_v1_prefix,
)


app.include_router(
    product_credentials_router,
    prefix=settings.api_v1_prefix,
)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "ayabot-backend",
        "environment": settings.app_env,
    }


@app.get("/", tags=["General"])
async def root():
    return {
        "message": "Welcome to AYABOT API",
        "description": "Internal AI assistant platform for Ayadi products",
        "docs": "/docs",
        "health": "/health",
    }

"""Smart Pricing Engine API. Dokumentasi OpenAPI: /api/v1/docs."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from pricing_engine import ENGINE_VERSION

from app.api import audit_logs, auth, costing, costs, organizations, planning, pricing, products
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.request_context import RequestIdMiddleware

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    get_settings().validate_for_runtime()
    app = FastAPI(
        title="Smart Pricing Engine API",
        version="0.2.0",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)

    @api.get("/health", tags=["system"])
    def health() -> dict:
        return {"success": True, "data": {"status": "ok", "engine_version": ENGINE_VERSION}}

    for module in (auth, organizations, products, costing, pricing, costs, planning, audit_logs):
        api.include_router(module.router)
    app.include_router(api)
    return app


app = create_app()

from fastapi import APIRouter

from . import routes_analyze, routes_authors, routes_claims

router = APIRouter(prefix="/api/v1")
router.include_router(routes_analyze.router)
router.include_router(routes_authors.router)
router.include_router(routes_claims.router)

__all__ = ["router"]

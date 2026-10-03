"""v1.3 Goal-centered product API, mounted under /api/product."""
from fastapi import APIRouter

from api.product.goals_router import router as goals_router
from api.product.insights_router import router as insights_router
from api.product.library_router import router as library_router
from api.product.session_router import router as session_router

router = APIRouter()
router.include_router(goals_router)
router.include_router(library_router)
router.include_router(session_router)
router.include_router(insights_router)


def init_product_layer() -> dict:
    """Create/upgrade product.db, seed role banks, migrate v1.2 prep spaces into Goals."""
    from services.product.goals import backfill_from_legacy
    from services.product.question_banks import ensure_builtin_banks
    from services.storage import product as store

    store.init_db()
    ensure_builtin_banks()
    return backfill_from_legacy()


__all__ = ["router", "init_product_layer"]

"""v1.3 Goal-centered product API, mounted under /api/product."""
from fastapi import APIRouter

from api.product.goals_router import router as goals_router
from api.product.insights_router import router as insights_router
from api.product.library_router import router as library_router
from api.product.session_router import router as session_router
from api.product.conversations_router import router as conversations_router

router = APIRouter()
router.include_router(goals_router)
router.include_router(library_router)
router.include_router(session_router)
router.include_router(insights_router)
router.include_router(conversations_router)


def init_product_layer() -> dict:
    """Create/upgrade product.db, seed role banks, migrate v1.2 prep spaces into Goals."""
    from services.product.goals import backfill_from_legacy
    from services.product.question_banks import ensure_builtin_banks
    from services.storage import product as store

    store.init_db()
    ensure_builtin_banks()
    backfill = backfill_from_legacy()

    # Real provider adapters remain explicit opt-in.  The GitHub adapter code
    # can ship without silently creating or connecting any external account.
    from services.product.github_connector import register_github_adapter_from_env
    from services.product.google_calendar_connector import register_google_calendar_adapter_from_env
    from services.product.google_drive_connector import register_google_drive_adapter_from_env
    from services.product.google_mail_connector import register_google_mail_adapter_from_env
    from services.product.microsoft_todo_connector import register_microsoft_todo_adapter_from_env

    github_connector = register_github_adapter_from_env()
    google_calendar_connector = register_google_calendar_adapter_from_env()
    google_drive_connector = register_google_drive_adapter_from_env()
    google_mail_connector = register_google_mail_adapter_from_env()
    microsoft_todo_connector = register_microsoft_todo_adapter_from_env()
    provider_state = {
        "github_connector": github_connector,
        "google_calendar_connector": google_calendar_connector,
        "google_drive_connector": google_drive_connector,
        "google_mail_connector": google_mail_connector,
        "microsoft_todo_connector": microsoft_todo_connector,
    }
    if isinstance(backfill, dict):
        return {**backfill, **provider_state}
    return {"backfill": backfill, **provider_state}


__all__ = ["router", "init_product_layer"]

from typing import Any

from .._logging import get_logger, warn_once

logger = get_logger(__name__)


def resolve_theme_manager(theme_manager: Any, caller: str) -> Any:
    if theme_manager is not None:
        return theme_manager

    try:
        from controller.app_context import get_theme_manager
    except ImportError as exc:
        warn_once(
            logger,
            f"{caller}:missing_app_context",
            "%s: app_context is unavailable, fallback to local LIGHT_TOKENS.",
            caller,
            exc_info=exc,
        )
        return None

    try:
        return get_theme_manager()
    except (AttributeError, RuntimeError) as exc:
        warn_once(
            logger,
            f"{caller}:get_theme_manager_failed",
            "%s: failed to get ThemeManager from app_context, fallback to local LIGHT_TOKENS.",
            caller,
            exc_info=exc,
        )
        return None

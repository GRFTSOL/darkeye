import logging
from threading import Lock

_ONCE_LOCK = Lock()
_ONCE_KEYS: set[str] = set()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def warn_once(logger: logging.Logger, key: str, message: str, *args, **kwargs) -> None:
    with _ONCE_LOCK:
        if key in _ONCE_KEYS:
            return
        _ONCE_KEYS.add(key)
    logger.warning(message, *args, **kwargs)

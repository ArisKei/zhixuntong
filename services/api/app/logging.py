import logging

import structlog


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # httpx logs complete request URLs at INFO. DingTalk Webhooks carry the
    # access token in the query string, so keep transport logs below WARNING.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    return structlog.get_logger(name)

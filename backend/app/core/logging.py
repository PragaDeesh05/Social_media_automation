import logging
import sys
import contextvars
from typing import Optional

correlation_id_ctx = contextvars.ContextVar[Optional[str]]("correlation_id", default=None)


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        cid = correlation_id_ctx.get()
        record.correlation_id = f"[{cid}]" if cid else "[sys]"
        return super().format(record)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger = logging.getLogger("incubrix")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = StructuredFormatter(
            fmt="%(asctime)s | %(levelname)-7s | %(correlation_id)s %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Suppress verbose noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    return logger


logger = setup_logging()

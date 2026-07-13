import logging
from pathlib import Path

DEFAULT_LOG_DIR: str = "logs"
DEFAULT_LOG_FILE: str = "tracerai.log"


def setup_logging(log_dir: str = DEFAULT_LOG_DIR, log_file: str = DEFAULT_LOG_FILE) -> logging.Logger:
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    log_path = path / log_file

    logger = logging.getLogger("tracerai")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("tracerai")

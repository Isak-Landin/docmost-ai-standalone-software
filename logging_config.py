# logging_config.py
import logging
import os
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler


def _parse_level(value: str) -> int:
    v = (value or "").strip().upper()
    if v in ("ALL", "DEBUG"):
        return logging.DEBUG
    if v == "INFO":
        return logging.INFO
    if v in ("WARN", "WARNING"):
        return logging.WARNING
    if v == "ERROR":
        return logging.ERROR
    if v == "CRITICAL":
        return logging.CRITICAL
    # Safe default if misconfigured
    return logging.INFO


class StaticContextFilter(logging.Filter):
    def __init__(self, service: str, mode: str):
        super().__init__()
        self._service = service
        self._mode = mode

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self._service
        record.mode = self._mode
        return True


def setup_logging(_service) -> None:
    mode = (os.getenv("MODE", "dev") or "dev").strip().lower()  # dev|prod
    service = _service
    level = _parse_level(os.getenv("LOG_LEVEL", "INFO"))

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Prevent duplicate handlers if called twice
    for h in list(root.handlers):
        root.removeHandler(h)

    ctx = StaticContextFilter(service=service, mode=mode)

    fmt = (
        "%(asctime)s | %(levelname)s | %(mode)s | %(service)s | "
        "%(name)s:%(lineno)d | %(message)s"
    )
    datefmt = "%Y-%m-%d %H:%M:%S"

    # Always log to console -> dev terminal + prod container logs
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.addFilter(ctx)
    console.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    root.addHandler(console)

    # File logging: only in prod (never in dev), controlled by MODE
    if mode == "prod":
        log_to_file = (os.getenv("LOG_TO_FILE", "1").strip() == "1")  # present, but prod-only
        if log_to_file:
            log_dir = os.getenv("LOG_DIR", "/var/log/app")
            os.makedirs(log_dir, exist_ok=True)

            # Base filename includes daily suffix as requested: backend-260223.log
            suffix = datetime.now().strftime("%y%m%d")
            filename = os.path.join(log_dir, f"{service}-{suffix}.log")

            # Rotate at midnight; keep N days.
            # Note: rotation will create additional files; that's standard behavior.
            fh = TimedRotatingFileHandler(
                filename=filename,
                when="midnight",
                interval=1,
                backupCount=int(os.getenv("LOG_KEEP_DAYS", "14")),
                encoding="utf-8",
                utc=False,
            )
            fh.setLevel(level)
            fh.addFilter(ctx)
            fh.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
            root.addHandler(fh)

    # Optional: silence noisy libs (adjust as needed)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
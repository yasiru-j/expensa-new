"""Structured logging: every log line is one JSON object (event + fields),
not free text, so upload/extraction/quota/rate-limit events can be grepped
or shipped to a log aggregator without a custom parser.

Deliberately never logs financial values — vendor, amounts, totals. Every
call site in this codebase passes only ids, statuses, counts, and
durations; grep for "log_event(" to audit this if adding a new call site.

TRD §9 asks for both structured logs and metrics (extraction success rate,
median latency, cost/extraction, quota-block rate). This app derives all of
those from the "extraction_attempt" log lines emitted below (outcome +
duration_ms + model + tier) rather than standing up a separate metrics
pipeline (Prometheus/Grafana etc.) — documented in the README as the
natural next step, not something a single-container demo app needs yet.
"""

import json
import logging
import sys


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if fields:
            payload.update(fields)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    logger.info(event, extra={"fields": fields})

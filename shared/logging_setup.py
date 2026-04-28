"""
Shared structured-logging setup (Kimi LOW-001 / L5).

Both URIP backend and the Compliance service install the same logging
configuration.  When the environment variable ``JSON_LOGS`` is set to a
truthy value (``true``, ``1``, ``yes``), each log record is emitted as
one JSON object per line; otherwise the standard human-readable format
is used.

Why structured logs?
--------------------
- SIEM / log-analysis pipelines (ELK, Loki, CloudWatch) can filter
  logs by structured fields (``tenant_id``, ``user_id``, ``action``)
  without regex acrobatics.
- Reduces accidental secret logging — formatting is explicit, not
  buried in f-strings.

Usage in callers
----------------
::

    from shared.logging_setup import install_json_logging
    install_json_logging()

    logger.info(
        "user.login",
        extra={"user_id": user.id, "tenant_id": tenant.id, "ip": request.client.host},
    )

The custom JSON formatter dumps the record's ``message``, level, name,
and any keys passed via ``extra=`` (excluding the standard LogRecord
attributes).
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


# LogRecord attributes set by the logging library that we DON'T want to
# duplicate into the JSON output.  Anything else passed via ``extra={…}``
# is preserved.
_STANDARD_LOGRECORD_ATTRS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
})


class JsonFormatter(logging.Formatter):
    """A minimal JSON formatter — no third-party deps."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Pull any caller-supplied "extra" fields onto the record.
        for key, value in record.__dict__.items():
            if key in _STANDARD_LOGRECORD_ATTRS or key.startswith("_"):
                continue
            try:
                json.dumps(value)  # ensure it's JSON-serialisable
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _json_logs_enabled() -> bool:
    return os.getenv("JSON_LOGS", "").strip().lower() in ("1", "true", "yes", "on")


def install_json_logging(level: int = logging.INFO) -> None:
    """
    Install a single root-logger handler with the JSON formatter (when
    JSON_LOGS=true) or a plain text formatter otherwise.  Idempotent —
    safe to call from both URIP backend and compliance service main().
    """
    root = logging.getLogger()
    # Replace any pre-existing handler that we previously installed so we
    # don't end up duplicating each line.
    for h in list(root.handlers):
        if getattr(h, "_urip_structured", False):
            root.removeHandler(h)

    handler = logging.StreamHandler(sys.stderr)
    handler._urip_structured = True  # marker for idempotency
    if _json_logs_enabled():
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s — %(message)s")
        )

    if not root.handlers:
        root.addHandler(handler)
    else:
        # If a handler already exists (uvicorn etc.), prepend ours so
        # JSON mode wins; do not remove uvicorn's handler — it has its
        # own access-log behaviour.
        root.addHandler(handler)

    root.setLevel(level)

"""Audit log writer.

Every completed assistant run -- every tool call and every guardrail decision --
is appended as one JSON line to `settings.audit_log_path` (append-only, JSONL).
This is the compliance-facing trail referenced in GOVERNANCE.md: it lets a
reviewer answer "what did the assistant tell client X, which tools did it call,
and did the guardrail intervene" after the fact.

This is a demo-grade append-only file, not a tamper-evident ledger; see
GOVERNANCE.md limitations for what a production system would add (WORM storage,
hash chaining, SIEM export, retention policy, etc).
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from app.domain.models import AuditLogEntry

logger = logging.getLogger("audit_log")


class AuditLogWriter:
    """Thread-safe append-only JSONL audit log writer."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, entry: AuditLogEntry) -> None:
        line = entry.model_dump_json()
        with self._lock, self._path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        logger.info(
            "audit_entry_written",
            extra={
                "client_id": entry.client_id,
                "run_id": entry.run_id,
                "guardrail_action": entry.guardrail_action.value,
                "tool_call_count": len(entry.tool_calls),
            },
        )

    def read_all(self) -> list[AuditLogEntry]:
        """Read back every audit entry -- used by tests and could back an internal
        `/audit` review endpoint in a fuller build."""
        if not self._path.exists():
            return []
        entries: list[AuditLogEntry] = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entries.append(AuditLogEntry.model_validate(json.loads(line)))
        return entries

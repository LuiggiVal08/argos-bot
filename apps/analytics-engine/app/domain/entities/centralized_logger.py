from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    level: LogLevel
    message: str
    component: str
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "message": self.message,
            "component": self.component,
            "context": self.context,
            "timestamp": self.timestamp,
        }


class CentralizedLogger:
    MAX_BUFFER = 5000

    def __init__(self) -> None:
        self._buffer: list[LogEntry] = []

    def log(
        self,
        level: LogLevel,
        message: str,
        component: str = "system",
        context: dict[str, Any] | None = None,
    ) -> None:
        entry = LogEntry(
            level=level,
            message=message,
            component=component,
            context=context or {},
        )
        self._buffer.append(entry)
        if len(self._buffer) > self.MAX_BUFFER:
            self._buffer = self._buffer[-self.MAX_BUFFER:]

    def debug(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.CRITICAL, message, **kwargs)

    def query(
        self,
        level: LogLevel | None = None,
        component: str | None = None,
        limit: int = 100,
    ) -> list[LogEntry]:
        result = list(self._buffer)
        if level:
            result = [e for e in result if e.level == level]
        if component:
            result = [e for e in result if e.component == component]
        return result[-limit:]

    def flush(self) -> list[LogEntry]:
        entries = list(self._buffer)
        self._buffer.clear()
        return entries

    @property
    def buffer_size(self) -> int:
        return len(self._buffer)

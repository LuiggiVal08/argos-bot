"""EnvironmentModeWriter port.

Writes the operational mode flag that gates LIVE/PAPER trading.

The DomainLayer does not know about the runtime flag — the
application layer translates a TRIP verdict into
"set mode to PASIVO". The infrastructure writes the flag in
whatever medium is appropriate for the deployment:
  - bare metal: write to a file (e.g. /var/lib/argos/env_mode).
  - Docker: set an env var on the next process restart (or
    signal via a /health response).
  - dev/test: in-memory attribute.

Sad path: any write failure raises EnvironmentModeError. The
use case treats this as a critical abort — without the env
flag flipped, the next iteration of the loop would still
dispatch orders.
"""
from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable


class EnvironmentMode(str, Enum):
    """The four runtime modes. Per AGENTS.md invariant #5, only
    these four are valid — PASIVO is the "halted" state set by
    the circuit breaker."""

    BACKTESTING = "BACKTESTING"
    PAPER_TRADING = "PAPER_TRADING"
    LIVE = "LIVE"
    PASIVO = "PASIVO"


class EnvironmentModeError(RuntimeError):
    """Raised when the mode can't be persisted."""


@runtime_checkable
class EnvironmentModeWriter(Protocol):
    async def write(self, mode: EnvironmentMode) -> None:
        """Persist the new mode. Raises EnvironmentModeError on
        failure. Idempotent (writing the same mode twice is a
        no-op)."""
        ...

    async def read(self) -> EnvironmentMode:
        """Read the current mode. Raises EnvironmentModeError on
        failure. Returns BACKTESTING as the safe default if the
        flag is unset (per spec: never auto-default to LIVE)."""
        ...

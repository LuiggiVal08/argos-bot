"""DrawdownSnapshotRepo port.

Stores the day's `starting_balance` so the use case can survive
restarts. The OpenDay use case calls `save(snapshot)`; the
CheckDrawdown use case calls `load()` to get the current
snapshot for evaluation.

Sad path: any I/O failure raises DrawdownSnapshotRepoError.
The use case aborts on this error (we'd rather halt trading
than run without a snapshot).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.value_objects.drawdown_snapshot import DrawdownSnapshot


class DrawdownSnapshotRepoError(RuntimeError):
    """Raised when the snapshot can't be read or written."""


@runtime_checkable
class DrawdownSnapshotRepo(Protocol):
    async def save(self, snapshot: DrawdownSnapshot) -> None:
        """Persist the snapshot for the current UTC day.
        Overwrites any previous snapshot for the day."""
        ...

    async def load(self) -> DrawdownSnapshot | None:
        """Returns the most recent snapshot, or None if no day
        has been opened yet. Raises DrawdownSnapshotRepoError
        on I/O failure."""
        ...

    async def clear(self) -> None:
        """Drop the stored snapshot. Used by the trip use case
        so the next day opens cleanly (or, in our model, the
        manual reset). Raises DrawdownSnapshotRepoError on
        I/O failure."""
        ...

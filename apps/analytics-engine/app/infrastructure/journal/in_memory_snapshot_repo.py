"""InMemorySnapshotRepo: stores the day's DrawdownSnapshot in a slot.

Used in BACKTESTING mode and tests. The repo holds at most one
snapshot; calling `save` overwrites it.
"""
from __future__ import annotations

from ...application.ports.drawdown_snapshot_repo import (
    DrawdownSnapshotRepo,
)
from ...domain.value_objects.drawdown_snapshot import DrawdownSnapshot


class InMemorySnapshotRepo(DrawdownSnapshotRepo):
    def __init__(self) -> None:
        self._snapshot: DrawdownSnapshot | None = None

    async def save(self, snapshot: DrawdownSnapshot) -> None:
        self._snapshot = snapshot

    async def load(self) -> DrawdownSnapshot | None:
        return self._snapshot

    async def clear(self) -> None:
        self._snapshot = None

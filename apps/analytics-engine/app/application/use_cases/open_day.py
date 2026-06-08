"""OpenDayUseCase.

Captures the day's starting balance and stores it in the
snapshot repo. Called:
  - At UTC 00:00 (by the scheduler — H3-FU1 will automate this).
  - After a circuit-breaker trip (to "open" the next day).
  - On a manual reset (operator action).

Sad path: if a snapshot already exists for the current day
(starting_balance > 0), we refuse to overwrite it. The caller
must call the reset endpoint first. This protects against a
stray scheduler tick that would reset the counters in the
middle of a losing day.
"""
from __future__ import annotations

from decimal import Decimal

from ...domain.value_objects.drawdown_snapshot import DrawdownSnapshot
from ..ports.balance_provider import (
    BalanceProvider,
    BalanceProviderError,
)
from ..ports.drawdown_snapshot_repo import (
    DrawdownSnapshotRepo,
    DrawdownSnapshotRepoError,
)


class OpenDayError(RuntimeError):
    """Raised when the day can't be opened (provider error,
    snapshot already exists, repo error)."""


class OpenDayUseCase:
    def __init__(
        self,
        balance_provider: BalanceProvider,
        snapshot_repo: DrawdownSnapshotRepo,
    ) -> None:
        self._balances = balance_provider
        self._snapshots = snapshot_repo

    async def execute(self, force: bool = False) -> DrawdownSnapshot:
        # Refuse to clobber an existing day unless explicitly forced.
        if not force:
            try:
                existing = await self._snapshots.load()
            except DrawdownSnapshotRepoError as e:
                raise OpenDayError(f"snapshot_unavailable: {e}") from e
            if existing is not None:
                raise OpenDayError(
                    f"snapshot_exists: starting_balance="
                    f"{existing.starting_balance}. Pass force=True to reset."
                )

        try:
            balance = await self._balances.get_free_balance()
        except BalanceProviderError as e:
            raise OpenDayError(f"balance_unavailable: {e}") from e

        snapshot = DrawdownSnapshot.at_open(balance)
        try:
            await self._snapshots.save(snapshot)
        except DrawdownSnapshotRepoError as e:
            raise OpenDayError(f"snapshot_save_failed: {e}") from e
        return snapshot

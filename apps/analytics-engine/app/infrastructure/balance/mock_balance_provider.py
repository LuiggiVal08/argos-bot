"""MockBalanceProvider: in-memory balance for BACKTESTING and tests.

Returns a fixed Decimal value regardless of input. The composition
root in BACKTESTING mode wires this instead of the CCXT provider.
Tests use it directly to assert the use case's sad path
behaviour without network.
"""
from __future__ import annotations

from decimal import Decimal

from ...application.ports.balance_provider import (
    BalanceProvider,
    BalanceProviderError,
)


class MockBalanceProvider(BalanceProvider):
    def __init__(self, free_balance: Decimal | float | int | str) -> None:
        self._value = Decimal(str(free_balance))

    async def get_free_balance(self, quote: str = "USDT") -> Decimal:
        if self._value <= 0:
            raise BalanceProviderError(
                f"mock_balance_invalid: {self._value} (must be > 0)"
            )
        return self._value

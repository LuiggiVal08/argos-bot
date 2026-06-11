"""Unit tests for the ComputePositionSizeUseCase.

Mocks all three ports (BalanceProvider, AtrCalculator, MinLotProvider)
so the test is hermetic and fast. Verifies the happy path and all
five sad paths from spec section 5 Historia 2.
"""
from decimal import Decimal
from typing import Awaitable, Callable
from unittest.mock import AsyncMock

import pytest

from app.application.ports.atr_calculator import (
    AtrCalculator,
    AtrCalculatorError,
)
from app.application.ports.balance_provider import (
    BalanceProvider,
    BalanceProviderError,
)
from app.application.ports.min_lot_provider import (
    MarketConstraints,
    MinLotProvider,
    MinLotProviderError,
)
from app.application.use_cases.compute_position_size import (
    ComputePositionSizeError,
    ComputePositionSizeUseCase,
    PositionSizeBelowMinLotError,
    PositionSizeInput,
)
from app.domain.entities.risk_calculator import RiskCalculator
from app.domain.value_objects.atr import Atr
from app.domain.value_objects.risk_pct import RiskPct


def make_balance(value: Decimal | Exception) -> BalanceProvider:
    bp = AsyncMock(spec=BalanceProvider)
    if isinstance(value, Exception):
        bp.get_free_balance.side_effect = value
    else:
        bp.get_free_balance.return_value = value
    return bp


def make_atr(value: Atr | Exception) -> AtrCalculator:
    ac = AsyncMock(spec=AtrCalculator)
    if isinstance(value, Exception):
        ac.get_atr.side_effect = value
    else:
        ac.get_atr.return_value = value
    return ac


def make_min_lot(
    constraints: MarketConstraints | Exception,
) -> MinLotProvider:
    ml = AsyncMock(spec=MinLotProvider)
    if isinstance(constraints, Exception):
        ml.get_constraints.side_effect = constraints
    else:
        ml.get_constraints.return_value = constraints
    return ml


@pytest.fixture
def use_case() -> ComputePositionSizeUseCase:
    return ComputePositionSizeUseCase(
        risk_calculator=RiskCalculator(),
        balance_provider=make_balance(Decimal("10000")),
        atr_calculator=make_atr(Atr(600)),
        min_lot_provider=make_min_lot(
            MarketConstraints(min_qty=0.0, qty_step=1e-8, min_notional=0.0)
        ),
    )


class TestComputePositionSizeHappyPath:
    @pytest.mark.asyncio
    async def test_returns_position_and_constraints(
        self, use_case: ComputePositionSizeUseCase
    ) -> None:
        inp = PositionSizeInput(
            symbol="BTC/USDT",
            entry_price=Decimal("60000"),
            risk_pct=RiskPct(0.01),
        )
        result = await use_case.execute(inp)
        # 10000 * 0.01 / 600 = 0.16666666... → quantised to 8dp = 0.16666667
        assert result.position.units == Decimal("0.16666667")
        assert result.position.sl_distance == Decimal("600")
        assert result.position.risk_amount == Decimal("100")
        assert result.constraints.min_qty == 0.0

    @pytest.mark.asyncio
    async def test_passes_through_atr_window_and_timeframe(
        self, use_case: ComputePositionSizeUseCase
    ) -> None:
        # Spy on the atr_calculator to confirm the params
        inp = PositionSizeInput(
            symbol="ETH/USDT",
            entry_price=Decimal("3000"),
            timeframe="5m",
            atr_window=20,
        )
        await use_case.execute(inp)
        use_case._atrs.get_atr.assert_awaited_once_with(  # type: ignore[attr-defined]
            "ETH/USDT", timeframe="5m", window=20
        )


class TestComputePositionSizeSadPaths:
    @pytest.mark.asyncio
    async def test_balance_provider_error_aborts(self) -> None:
        uc = ComputePositionSizeUseCase(
            risk_calculator=RiskCalculator(),
            balance_provider=make_balance(
                BalanceProviderError("ccxt timeout")
            ),
            atr_calculator=make_atr(Atr(600)),
            min_lot_provider=make_min_lot(
                MarketConstraints(0.0, 1e-8, 0.0)
            ),
        )
        with pytest.raises(ComputePositionSizeError) as exc:
            await uc.execute(
                PositionSizeInput(symbol="BTC/USDT", entry_price=Decimal("60000"))
            )
        assert "balance_unavailable" in str(exc.value)

    @pytest.mark.asyncio
    async def test_atr_calculator_error_aborts(self) -> None:
        uc = ComputePositionSizeUseCase(
            risk_calculator=RiskCalculator(),
            balance_provider=make_balance(Decimal("10000")),
            atr_calculator=make_atr(
                AtrCalculatorError("insufficient_candles")
            ),
            min_lot_provider=make_min_lot(
                MarketConstraints(0.0, 1e-8, 0.0)
            ),
        )
        with pytest.raises(ComputePositionSizeError) as exc:
            await uc.execute(
                PositionSizeInput(symbol="BTC/USDT", entry_price=Decimal("60000"))
            )
        assert "atr_unavailable" in str(exc.value)

    @pytest.mark.asyncio
    async def test_min_lot_provider_error_aborts(self) -> None:
        uc = ComputePositionSizeUseCase(
            risk_calculator=RiskCalculator(),
            balance_provider=make_balance(Decimal("10000")),
            atr_calculator=make_atr(Atr(600)),
            min_lot_provider=make_min_lot(
                MinLotProviderError("network")
            ),
        )
        with pytest.raises(ComputePositionSizeError) as exc:
            await uc.execute(
                PositionSizeInput(symbol="BTC/USDT", entry_price=Decimal("60000"))
            )
        assert "min_lot_unavailable" in str(exc.value)

    @pytest.mark.asyncio
    async def test_below_min_qty_discards_signal(self) -> None:
        # 10,000 balance, 1% risk = 100 risk_amount.
        # With ATR 600 that's 0.16666666 units. If min_qty=1, discard.
        uc = ComputePositionSizeUseCase(
            risk_calculator=RiskCalculator(),
            balance_provider=make_balance(Decimal("10000")),
            atr_calculator=make_atr(Atr(600)),
            min_lot_provider=make_min_lot(
                MarketConstraints(min_qty=1.0, qty_step=1e-8, min_notional=0.0)
            ),
        )
        with pytest.raises(PositionSizeBelowMinLotError):
            await uc.execute(
                PositionSizeInput(symbol="BTC/USDT", entry_price=Decimal("60000"))
            )

    @pytest.mark.asyncio
    async def test_below_min_notional_discards_signal(self) -> None:
        # 10,000 * 1% / 600 = 0.166... units * 60,000 = ~10,000 notional.
        # Set min_notional to 20,000 → discard.
        uc = ComputePositionSizeUseCase(
            risk_calculator=RiskCalculator(),
            balance_provider=make_balance(Decimal("10000")),
            atr_calculator=make_atr(Atr(600)),
            min_lot_provider=make_min_lot(
                MarketConstraints(min_qty=0.0, qty_step=1e-8, min_notional=20000.0)
            ),
        )
        with pytest.raises(PositionSizeBelowMinLotError) as exc:
            await uc.execute(
                PositionSizeInput(symbol="BTC/USDT", entry_price=Decimal("60000"))
            )
        assert "min_notional" in str(exc.value)

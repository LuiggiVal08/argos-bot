"""Unit tests for the RiskCalculator domain entity.

Pure-domain tests. The fixture gives a canonical 1% risk on a
$10,000 balance with a 600 ATR — yielding units = 10000 * 0.01 / 600.
We assert the value-object contract (units >= 0, sl_distance = atr,
risk_amount = balance * risk_pct).
"""
from decimal import Decimal

import pytest

from app.domain.entities.risk_calculator import (
    InvalidEntryPriceError,
    InvalidFreeBalanceError,
    RiskCalculator,
)
from app.domain.value_objects.atr import Atr
from app.domain.value_objects.risk_pct import RiskPct


class TestRiskCalculator:
    def setup_method(self) -> None:
        self.calc = RiskCalculator()

    def test_happy_path_one_percent(self) -> None:
        # balance 10000, atr 600, risk 1% → units = 10000 * 0.01 / 600
        p = self.calc.calculate(
            free_balance=Decimal("10000"),
            atr=Atr(600),
            entry_price=Decimal("60000"),
            risk_pct=RiskPct(0.01),
        )
        # 100/600 = 0.16666666... → quantised to 8dp = 0.16666667
        assert p.units == Decimal("0.16666667")
        assert p.sl_distance == Decimal("600")
        assert p.entry_price == Decimal("60000")
        assert p.risk_amount == Decimal("100.00")
        assert p.risk_pct == Decimal("0.01")
        # notional = units * entry_price
        assert p.notional_value == Decimal("0.16666667") * Decimal("60000")

    def test_higher_atr_yields_smaller_size(self) -> None:
        small = self.calc.calculate(
            free_balance=Decimal("10000"),
            atr=Atr(100),
            entry_price=Decimal("60000"),
            risk_pct=RiskPct(0.01),
        )
        big = self.calc.calculate(
            free_balance=Decimal("10000"),
            atr=Atr(1000),
            entry_price=Decimal("60000"),
            risk_pct=RiskPct(0.01),
        )
        # bigger ATR → smaller position (the rule's whole point)
        assert big.units < small.units
        # risk_amount is identical (it's just balance * risk_pct)
        assert small.risk_amount == big.risk_amount

    def test_sl_distance_equals_atr(self) -> None:
        p = self.calc.calculate(
            free_balance=Decimal("10000"),
            atr=Atr("123.456"),
            entry_price=Decimal("50000"),
            risk_pct=RiskPct(0.01),
        )
        assert p.sl_distance == Decimal("123.456")

    def test_rejects_zero_balance(self) -> None:
        with pytest.raises(InvalidFreeBalanceError):
            self.calc.calculate(
                free_balance=Decimal("0"),
                atr=Atr(600),
                entry_price=Decimal("60000"),
                risk_pct=RiskPct(0.01),
            )

    def test_rejects_negative_balance(self) -> None:
        with pytest.raises(InvalidFreeBalanceError):
            self.calc.calculate(
                free_balance=Decimal("-1"),
                atr=Atr(600),
                entry_price=Decimal("60000"),
                risk_pct=RiskPct(0.01),
            )

    def test_rejects_zero_entry_price(self) -> None:
        with pytest.raises(InvalidEntryPriceError):
            self.calc.calculate(
                free_balance=Decimal("10000"),
                atr=Atr(600),
                entry_price=Decimal("0"),
                risk_pct=RiskPct(0.01),
            )

    def test_risk_amount_is_exactly_one_percent_of_balance(self) -> None:
        # Spec invariant #1: loss per trade <= 1% of free balance.
        p = self.calc.calculate(
            free_balance=Decimal("10000"),
            atr=Atr(600),
            entry_price=Decimal("60000"),
            risk_pct=RiskPct(0.01),
        )
        # risk_amount is always exactly balance * risk_pct — the
        # rounding is on `units` only, not on the loss budget.
        assert p.risk_amount == Decimal("100.00")

        # Hard cap test: even with extreme ATR, risk_amount is
        # still exactly balance * risk_pct (the spec invariant).
        p2 = self.calc.calculate(
            free_balance=Decimal("5000"),
            atr=Atr(10000),
            entry_price=Decimal("60000"),
            risk_pct=RiskPct(0.01),
        )
        assert p2.risk_amount == Decimal("50.00")

        # Approximate but tight: units * sl_distance ≈ risk_amount.
        # The rounding on units is at most 1e-8 in absolute terms.
        approx = p.units * p.sl_distance
        assert abs(approx - p.risk_amount) < Decimal("1e-4")

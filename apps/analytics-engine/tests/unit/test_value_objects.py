"""Unit tests for the domain VOs (Atr, RiskPct, PositionSize).

Pure-domain tests: no I/O, no fixtures, no mocks. These are the
fastest tests in the suite and form the foundation for the use
case and adapter tests.
"""
from decimal import Decimal

import pytest

from app.domain.value_objects.atr import Atr, InvalidAtrError
from app.domain.value_objects.position_size import PositionSize
from app.domain.value_objects.risk_pct import (
    DEFAULT_RISK_PCT,
    MAX_RISK_PCT,
    InvalidRiskPctError,
    RiskPct,
)


class TestAtr:
    def test_accepts_positive_decimal(self) -> None:
        a = Atr("123.45")
        assert a.value == Decimal("123.45")

    def test_accepts_int(self) -> None:
        a = Atr(100)
        assert a.value == Decimal("100")

    def test_accepts_float_close_to_decimal(self) -> None:
        # Floats are coerced via str() so we don't get drift on
        # values that have an exact decimal representation.
        a = Atr(0.5)
        assert a.value == Decimal("0.5")

    def test_rejects_zero(self) -> None:
        with pytest.raises(InvalidAtrError):
            Atr(0)

    def test_rejects_negative(self) -> None:
        with pytest.raises(InvalidAtrError):
            Atr("-0.01")

    def test_rejects_too_many_decimals(self) -> None:
        with pytest.raises(InvalidAtrError):
            Atr("0." + "0" * 18 + "1")  # 19 decimals, exceeds cap of 18

    def test_equality_is_value_based(self) -> None:
        assert Atr("1.0") == Atr(1)

    def test_hash_matches_equality(self) -> None:
        assert hash(Atr("1.0")) == hash(Atr(1))


class TestRiskPct:
    def test_default_is_one_percent(self) -> None:
        assert RiskPct.default().value == DEFAULT_RISK_PCT

    def test_accepts_one_percent(self) -> None:
        r = RiskPct(0.01)
        assert r.value == Decimal("0.01")

    def test_accepts_two_percent_at_the_cap(self) -> None:
        r = RiskPct(MAX_RISK_PCT)
        assert r.value == MAX_RISK_PCT

    def test_rejects_zero(self) -> None:
        with pytest.raises(InvalidRiskPctError):
            RiskPct(0)

    def test_rejects_negative(self) -> None:
        with pytest.raises(InvalidRiskPctError):
            RiskPct(-0.01)

    def test_rejects_above_cap(self) -> None:
        with pytest.raises(InvalidRiskPctError, match="exceeds"):
            RiskPct(0.021)

    def test_rejects_obviously_wrong_values(self) -> None:
        # 5% is a 5x violation of the spec cap. Must reject.
        with pytest.raises(InvalidRiskPctError):
            RiskPct(0.05)

    def test_rejects_one_hundred_percent(self) -> None:
        with pytest.raises(InvalidRiskPctError):
            RiskPct(1.0)


class TestPositionSize:
    def test_to_dict_roundtrips_via_strings(self) -> None:
        p = PositionSize(
            units=Decimal("0.01666666"),
            sl_distance=Decimal("600.00"),
            entry_price=Decimal("60000.00"),
            notional_value=Decimal("999.996"),
            risk_amount=Decimal("100.00"),
            risk_pct=Decimal("0.01"),
        )
        d = p.to_dict()
        assert d["units"] == "0.01666666"
        assert d["sl_distance"] == "600.00"
        assert d["risk_pct"] == "0.01"

    def test_rejects_negative_units(self) -> None:
        with pytest.raises(ValueError):
            PositionSize(
                units=Decimal("-1"),
                sl_distance=Decimal("600"),
                entry_price=Decimal("60000"),
                notional_value=Decimal("0"),
                risk_amount=Decimal("0"),
                risk_pct=Decimal("0.01"),
            )

    def test_rejects_negative_sl_distance(self) -> None:
        with pytest.raises(ValueError):
            PositionSize(
                units=Decimal("0"),
                sl_distance=Decimal("-1"),
                entry_price=Decimal("60000"),
                notional_value=Decimal("0"),
                risk_amount=Decimal("0"),
                risk_pct=Decimal("0.01"),
            )

    def test_rejects_negative_entry_price(self) -> None:
        with pytest.raises(ValueError):
            PositionSize(
                units=Decimal("0"),
                sl_distance=Decimal("600"),
                entry_price=Decimal("-1"),
                notional_value=Decimal("0"),
                risk_amount=Decimal("0"),
                risk_pct=Decimal("0.01"),
            )

    def test_is_immutable(self) -> None:
        p = PositionSize(
            units=Decimal("1"),
            sl_distance=Decimal("600"),
            entry_price=Decimal("60000"),
            notional_value=Decimal("60000"),
            risk_amount=Decimal("100"),
            risk_pct=Decimal("0.01"),
        )
        with pytest.raises(Exception):
            p.units = Decimal("0")  # type: ignore[misc]

"""Tests for CorrelationEngine domain entity (H36)."""
from decimal import Decimal

import pytest

from app.domain.entities.correlation_engine import CorrelationEngine


class TestCorrelationEngine:
    def test_pearson_identical_returns_one(self):
        prices = [Decimal(str(i)) for i in range(100, 200)]
        corr = CorrelationEngine.pearson(prices, prices)
        assert corr >= Decimal("0.9999")

    def test_pearson_inverse_returns(self):
        # Build series where returns are exact opposites
        a: list[Decimal] = [Decimal("100"), Decimal("110"),
                            Decimal("115"), Decimal("130")]
        b: list[Decimal] = [Decimal("100")]
        for i in range(1, len(a)):
            ratio = a[i] / a[i - 1]
            b.append(b[-1] * (Decimal("2") - ratio))
        corr = CorrelationEngine.pearson(a, b)
        assert corr <= Decimal("-0.9999")

    def test_pearson_uncorrelated(self):
        import random
        random.seed(42)
        a = [Decimal(str(random.gauss(0, 1))) for _ in range(100)]
        b = [Decimal(str(random.gauss(0, 1))) for _ in range(100)]
        corr = CorrelationEngine.pearson(a, b)
        # Should be near 0 for random independent series
        assert Decimal("-0.5") < corr < Decimal("0.5")

    def test_pearson_few_points(self):
        prices_a = [Decimal("100"), Decimal("101"), Decimal("102")]
        prices_b = [Decimal("200"), Decimal("201"), Decimal("203")]
        corr = CorrelationEngine.pearson(prices_a, prices_b)
        assert Decimal("-1") <= corr <= Decimal("1")

    def test_pearson_less_than_two_points(self):
        with pytest.raises(ValueError, match="at least 2"):
            CorrelationEngine.pearson([Decimal("100")], [Decimal("200")])

    def test_pearson_mismatched_lengths(self):
        with pytest.raises(ValueError, match="must match"):
            CorrelationEngine.pearson(
                [Decimal("100"), Decimal("101")],
                [Decimal("200")],
            )

    def test_pearson_constant_series(self):
        prices = [Decimal("100")] * 10
        corr = CorrelationEngine.pearson(prices, prices)
        assert corr == Decimal("0")

    def test_correlation_matrix_three_symbols(self):
        a = [Decimal("100"), Decimal("110"), Decimal("115"), Decimal("130")]
        b = [Decimal("100"), Decimal("110"), Decimal("115"), Decimal("130")]
        # Build SOL with inverse returns of BTC
        sol: list[Decimal] = [Decimal("100")]
        for i in range(1, len(a)):
            ratio = a[i] / a[i - 1]
            sol.append(sol[-1] * (Decimal("2") - ratio))

        series = {
            "BTC/USDT": a,
            "ETH/USDT": b,
            "SOL/USDT": sol,
        }
        matrix = CorrelationEngine.correlation_matrix(series)

        assert "BTC/USDT" in matrix
        assert "ETH/USDT" in matrix
        assert "SOL/USDT" in matrix

        # Diagonal should be 1
        assert matrix["BTC/USDT"]["BTC/USDT"] == Decimal("1")
        assert matrix["ETH/USDT"]["ETH/USDT"] == Decimal("1")

        # BTC ~ ETH should be perfectly correlated (same prices)
        assert matrix["BTC/USDT"]["ETH/USDT"] >= Decimal("0.99")

        # BTC ~ SOL should be perfectly inversely correlated
        assert matrix["BTC/USDT"]["SOL/USDT"] <= Decimal("-0.99")

        # Symmetry
        assert matrix["BTC/USDT"]["ETH/USDT"] == matrix["ETH/USDT"]["BTC/USDT"]

    def test_returns_length(self):
        prices = [Decimal("100"), Decimal("110"), Decimal("105")]
        returns = CorrelationEngine._returns(prices)
        assert len(returns) == 2

    def test_returns_with_zero_price(self):
        # zero prev price should be skipped
        prices = [Decimal("0"), Decimal("110"), Decimal("105")]
        returns = CorrelationEngine._returns(prices)
        assert len(returns) == 1

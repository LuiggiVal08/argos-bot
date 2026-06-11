"""Domain entity: CorrelationEngine.

Cross-asset correlation computation (H36).

Pure math: receives price arrays and returns Pearson correlation.
No I/O, no side effects.

The application layer is responsible for fetching the historical
price data through a repository port.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from math import sqrt


class CorrelationEngine:
    """Pure-domain correlation calculator.

    Computes Pearson correlation coefficient between two price series.
    Thread-safe, stateless.
    """

    @staticmethod
    def pearson(prices_a: list[Decimal], prices_b: list[Decimal]) -> Decimal:
        """Pearson correlation coefficient between two price arrays.

        Both arrays must have the same length (>= 2).
        Returns value in [-1, 1].
        Raises ValueError if inputs are invalid.
        """
        n = len(prices_a)
        if n < 2:
            raise ValueError(f"need at least 2 data points, got {n}")
        if n != len(prices_b):
            raise ValueError(
                f"price arrays must match, got {n} vs {len(prices_b)}"
            )

        # Convert to returns for stationarity
        returns_a = CorrelationEngine._returns(prices_a)
        returns_b = CorrelationEngine._returns(prices_b)

        if len(returns_a) < 2:
            return Decimal("0")

        n_r = len(returns_a)
        sum_a = sum(returns_a)
        sum_b = sum(returns_b)
        sum_ab = sum(a * b for a, b in zip(returns_a, returns_b))
        sum_a2 = sum(a * a for a in returns_a)
        sum_b2 = sum(b * b for b in returns_b)

        numerator = n_r * sum_ab - sum_a * sum_b
        denom_a = n_r * sum_a2 - sum_a * sum_a
        denom_b = n_r * sum_b2 - sum_b * sum_b

        if denom_a <= 0 or denom_b <= 0:
            return Decimal("0")

        denom = Decimal(str(sqrt(float(denom_a * denom_b))))
        if denom == 0:
            return Decimal("0")

        result = numerator / denom
        # Clamp to [-1, 1]
        return max(Decimal("-1"), min(Decimal("1"), result)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    @staticmethod
    def _returns(prices: list[Decimal]) -> list[Decimal]:
        """Compute period-over-period returns."""
        if len(prices) < 2:
            return []
        result: list[Decimal] = []
        for i in range(1, len(prices)):
            prev = prices[i - 1]
            if prev == 0:
                continue
            ret = (prices[i] - prev) / prev
            result.append(ret)
        return result

    @staticmethod
    def correlation_matrix(
        price_series: dict[str, list[Decimal]],
    ) -> dict[str, dict[str, Decimal]]:
        """Compute correlation matrix for multiple symbols.

        Returns {symbol_a: {symbol_b: correlation}}.
        Diagonal entries are 1.0.
        """
        symbols = list(price_series.keys())
        matrix: dict[str, dict[str, Decimal]] = {}

        for sym_a in symbols:
            matrix[sym_a] = {}
            for sym_b in symbols:
                if sym_a == sym_b:
                    matrix[sym_a][sym_b] = Decimal("1")
                elif sym_b in matrix and sym_a in matrix[sym_b]:
                    matrix[sym_a][sym_b] = matrix[sym_b][sym_a]
                else:
                    corr = CorrelationEngine.pearson(
                        price_series[sym_a], price_series[sym_b]
                    )
                    matrix[sym_a][sym_b] = corr

        return matrix

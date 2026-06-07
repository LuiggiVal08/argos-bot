"""ATR (Average True Range) value object.

ATR is the canonical volatility measure for H2's stop-loss distance
calculation. Per spec invariant #2, the SL distance is derived from
ATR, not from a fixed percentage.

Stored as Decimal to avoid float drift across arithmetic and JSON
serialisation. The contract is:
  - atr > 0 (a zero ATR would mean no volatility = division by zero
    in the position-size formula).
  - atr has at most 12 decimal places (sub-pip granularity is
    meaningless for crypto).
"""
from __future__ import annotations

from decimal import Decimal


class InvalidAtrError(ValueError):
    """Raised when ATR construction receives a non-positive value or
    a value with too much precision."""


_MAX_DECIMALS = 18


class Atr:
    __slots__ = ("_value",)

    def __init__(self, value: Decimal | float | int | str) -> None:
        d = Decimal(str(value)) if not isinstance(value, Decimal) else value
        if d <= 0:
            raise InvalidAtrError(f"ATR must be > 0, got {d}")
        # as_tuple().exponent is `int | str` in the type stub (str
        # for NaN/Infinity). NaN was already excluded by `d <= 0`,
        # so cast to int. mypy: see https://github.com/python/typeshed/issues/8588
        exponent = int(d.as_tuple().exponent)  # type: ignore[arg-type]
        if -exponent > _MAX_DECIMALS:
            raise InvalidAtrError(
                f"ATR has more than {_MAX_DECIMALS} decimal places: {d}"
            )
        self._value = d

    @property
    def value(self) -> Decimal:
        return self._value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Atr) and self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return f"Atr({self._value})"

    def __str__(self) -> str:
        return str(self._value)

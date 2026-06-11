"""Domain Entity: BacktestEngine — motor de simulacion historica.

Procesa velas OHLCV secuencialmente, llama a la estrategia para
obtener senales, simula entrada/salida de posiciones, calcula PnL,
y produce una lista de trades mas la curva de equity.

El motor es agnostico de la estrategia: recibe un callable que
dado el indice de la vela actual y todo el historico disponible
retorna un TradingSignal (o None para saltar).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable

from ..value_objects.backtest_config import BacktestConfig
from ..value_objects.backtest_trade import BacktestTrade
from ..value_objects.signal_side import SignalSide


EquityPoint = tuple[datetime, Decimal]
"""Punto de la curva de equity: (timestamp, balance)."""

SignalFn = Callable[
    [int, list[dict], BacktestConfig],
    tuple[SignalSide, float] | None,
]
"""Funcion de senal: recibe (indice_actual, ohlcv, config) y retorna
(side, confidence) o None si no hay senal.
"""


class BacktestError(RuntimeError):
    """Raised when the backtest engine encounters an unrecoverable error."""


@dataclass
class BacktestEngine:
    """Simula trades sobre datos historicos.

    Uso:
        engine = BacktestEngine()
        trades, equity = engine.run(ohlcv, config, signal_fn)
    """

    def run(
        self,
        ohlcv: list[dict],
        config: BacktestConfig,
        signal_fn: SignalFn,
    ) -> tuple[list[BacktestTrade], list[EquityPoint]]:
        """Ejecuta el backtest sobre las velas dadas.

        Args:
            ohlcv: Lista de velas (dict con timestamp, open, high, low, close, volume).
            config: Configuracion del backtest.
            signal_fn: Funcion que genera senales para cada vela.

        Returns:
            Tuple de (trades, equity_curve).
        """
        if len(ohlcv) < 50:
            raise BacktestError(
                f"insufficient_candles: need at least 50, got {len(ohlcv)}"
            )

        trades: list[BacktestTrade] = []
        equity_curve: list[EquityPoint] = []
        balance = config.initial_balance
        position: _Position | None = None
        trade_count = 0

        for i in range(len(ohlcv)):
            candle = ohlcv[i]
            ts = self._parse_ts(candle)

            # Equity curve snapshot
            equity_curve.append((ts, balance))

            # Generar senal
            signal = signal_fn(i, ohlcv, config)

            # Gestion de posicion
            if position is not None:
                # Check stop loss
                sl_hit = self._check_stop_loss(candle, position)

                # Check exit signal (opposite side)
                exit_signal = (
                    signal is not None
                    and signal[0] != position.side
                    and signal[0] != SignalSide.HOLD
                    and signal[1] >= 0.5
                )

                if sl_hit or exit_signal:
                    exit_price = Decimal(str(candle["close"]))
                    trade = self._close_trade(
                        position=position,
                        exit_time=ts,
                        exit_price=exit_price,
                        exit_reason="stop_loss" if sl_hit else "exit_signal",
                    )
                    trades.append(trade)
                    balance += trade.pnl
                    position = None
                    continue

            # Entry signal
            if position is None and signal is not None:
                side, confidence = signal
                if side != SignalSide.HOLD and confidence >= 0.5:
                    entry_price = Decimal(str(candle["close"]))
                    if entry_price <= Decimal("0"):
                        continue
                    atr = self._calc_atr(ohlcv, i, period=14)
                    sl_distance = max(atr * Decimal("1.5"), entry_price * Decimal("0.005"))

                    risk_amount = balance * config.risk_pct
                    position_value = risk_amount / Decimal("0.01")
                    units_raw = position_value / entry_price
                    units = units_raw.quantize(Decimal("0.00001"))

                    sl_price = entry_price - sl_distance if side == SignalSide.BUY else entry_price + sl_distance
                    if sl_price <= Decimal("0"):
                        sl_price = entry_price * Decimal("0.95")

                    position = _Position(
                        side=side,
                        entry_time=ts,
                        entry_price=entry_price,
                        units=units,
                        sl_price=sl_price,
                        balance_at_entry=balance,
                        entry_reason=f"signal_{side.value}_conf_{confidence:.2f}",
                    )
                    trade_count += 1

            if config.max_trades > 0 and trade_count >= config.max_trades:
                # Close any open position at last candle
                if position is not None:
                    exit_price = Decimal(str(candle["close"]))
                    trade = self._close_trade(
                        position=position,
                        exit_time=ts,
                        exit_price=exit_price,
                        exit_reason="max_trades_reached",
                    )
                    trades.append(trade)
                    balance += trade.pnl
                    position = None
                break

        # Close any remaining position at last candle
        if position is not None:
            last = ohlcv[-1]
            exit_price = Decimal(str(last["close"]))
            trade = self._close_trade(
                position=position,
                exit_time=self._parse_ts(last),
                exit_price=exit_price,
                exit_reason="end_of_data",
            )
            trades.append(trade)
            balance += trade.pnl

        return trades, equity_curve

    @staticmethod
    def _parse_ts(candle: dict) -> datetime:
        ts = candle.get("timestamp", 0)
        if isinstance(ts, (int, float)):
            if ts > 1e12:
                ts = ts / 1000
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        if isinstance(ts, str):
            return datetime.fromisoformat(ts)
        return ts

    @staticmethod
    def _calc_atr(ohlcv: list[dict], idx: int, period: int = 14) -> Decimal:
        """Calcula ATR simple sobre las ultimas `period` velas."""
        start = max(0, idx - period)
        if idx - start < 2:
            return Decimal("0")
        total = Decimal("0")
        count = 0
        for j in range(start + 1, idx + 1):
            high = Decimal(str(ohlcv[j]["high"]))
            low = Decimal(str(ohlcv[j]["low"]))
            prev_close = Decimal(str(ohlcv[j - 1]["close"]))
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )
            total += tr
            count += 1
        return total / Decimal(str(count)) if count > 0 else Decimal("0")

    @staticmethod
    def _check_stop_loss(candle: dict, position: _Position) -> bool:
        """True si la vela toca el stop loss."""
        low = Decimal(str(candle["low"]))
        high = Decimal(str(candle["high"]))
        if position.side == SignalSide.BUY:
            return low <= position.sl_price
        return high >= position.sl_price

    @staticmethod
    def _close_trade(
        position: _Position,
        exit_time: datetime,
        exit_price: Decimal,
        exit_reason: str,
    ) -> BacktestTrade:
        if position.side == SignalSide.BUY:
            pnl = (exit_price - position.entry_price) * position.units
        else:
            pnl = (position.entry_price - exit_price) * position.units

        invested = position.entry_price * position.units
        pnl_pct = (pnl / invested * 100) if invested > 0 else Decimal("0")
        duration = int((exit_time - position.entry_time).total_seconds() / 60)

        return BacktestTrade(
            side=position.side,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            exit_time=exit_time,
            exit_price=exit_price,
            units=position.units,
            pnl=pnl.quantize(Decimal("0.01")),
            pnl_pct=pnl_pct.quantize(Decimal("0.01")),
            entry_reason=position.entry_reason,
            exit_reason=exit_reason,
            duration_min=duration,
        )


@dataclass
class _Position:
    """Posicion abierta durante el backtest."""
    side: SignalSide
    entry_time: datetime
    entry_price: Decimal
    units: Decimal
    sl_price: Decimal
    balance_at_entry: Decimal
    entry_reason: str = ""

"""Frozen port of the 2Lotus ZigZag Scalper V1.0 trigger geometry."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .contracts import Candle, MarketSnapshot, Side, SignalCandidate


COMPONENT_ID = "trigger.g01"
SOURCE = "2Lotus@2e5a0fa:happy_gold_zigzag_scalper"


def aggregate_completed_candles(candles: tuple[Candle, ...], timeframe_minutes: int, available_at: datetime) -> list[Candle]:
    buckets: dict[datetime, list[Candle]] = defaultdict(list)
    for candle in sorted(candles, key=lambda item: item.timestamp_utc):
        timestamp = candle.timestamp_utc.astimezone(timezone.utc)
        bucket_minute = timestamp.minute - timestamp.minute % timeframe_minutes
        bucket_start = timestamp.replace(minute=bucket_minute, second=0, microsecond=0)
        if bucket_start + timedelta(minutes=timeframe_minutes) <= available_at.astimezone(timezone.utc):
            buckets[bucket_start].append(candle)
    return [
        Candle(start, rows[0].open, max(row.high for row in rows), min(row.low for row in rows), rows[-1].close, sum(row.volume for row in rows))
        for start, rows in sorted(buckets.items())
    ]


def latest_confirmed_zigzag_levels(candles: list[Candle], span: int = 2) -> tuple[float | None, float | None]:
    pivot_high: float | None = None
    pivot_low: float | None = None
    for index in range(span, len(candles) - span):
        window = candles[index - span:index + span + 1]
        current = candles[index]
        if current.high == max(candle.high for candle in window):
            pivot_high = current.high
        if current.low == min(candle.low for candle in window):
            pivot_low = current.low
    return pivot_high, pivot_low


def evaluate(snapshot: MarketSnapshot) -> SignalCandidate | None:
    if snapshot.symbol.upper() != "XAUUSD" or len(snapshot.candles) < 43:
        return None
    m30 = aggregate_completed_candles(snapshot.candles, 30, snapshot.timestamp_utc)
    if len(m30) < 7:
        return None
    pivot_high, pivot_low = latest_confirmed_zigzag_levels(m30)
    previous_close = snapshot.candles[-2].close
    buy = pivot_high is not None and previous_close <= pivot_high < snapshot.ask
    sell = pivot_low is not None and previous_close >= pivot_low > snapshot.bid
    if not buy and not sell:
        return None
    if buy and sell:
        buy = snapshot.ask - float(pivot_high) >= float(pivot_low) - snapshot.bid
        sell = not buy
    side = Side.BUY if buy else Side.SELL
    entry = snapshot.ask if buy else snapshot.bid
    stop_points, target_points = 240.0, 1000.0
    direction = 1 if buy else -1
    return SignalCandidate(
        component_id=COMPONENT_ID,
        side=side,
        entry=entry,
        stop=entry - direction * stop_points * snapshot.point_size,
        target=entry + direction * target_points * snapshot.point_size,
        stop_points=stop_points,
        target_points=target_points,
        valid_until=snapshot.timestamp_utc + timedelta(minutes=10),
        metadata={
            "setup_type": "happy_gold_zigzag_breakout",
            "breakout_level": float(pivot_high if buy else pivot_low),
            "signal_timeframe": "M30",
            "execution_timeframe": "M5",
            "max_holding_bars": 2,
            "source": SOURCE,
        },
    )

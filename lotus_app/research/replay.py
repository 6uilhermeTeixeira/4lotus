from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterator

import duckdb

from ..dataset import DatasetError, GoldHistory
from .contracts import Candle, MarketSnapshot, TickQuote
from .pipeline import ResearchPipeline
from .zigzag_v1 import aggregate_completed_candles, latest_confirmed_zigzag_levels


@dataclass(slots=True)
class ReplayResult:
    dataset_version: str
    start: str
    end: str
    ticks_evaluated: int
    signals: list[dict[str, object]]

    def as_dict(self) -> dict[str, object]:
        buy_count = sum(signal["action"] == "buy" for signal in self.signals)
        sell_count = len(self.signals) - buy_count
        return {
            "dataset_version": self.dataset_version,
            "start": self.start,
            "end": self.end,
            "ticks_evaluated": self.ticks_evaluated,
            "signal_count": len(self.signals),
            "metrics": {"buy_signals": buy_count, "sell_signals": sell_count, "approved_signals": len(self.signals)},
            "parameters": {"point_size": 0.01, "max_signals_returned": 500},
            "signals": self.signals,
        }


def _paths(root: Path, entries: object, start: date, end: date) -> list[str]:
    result: list[str] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or not isinstance(entry.get("day"), str) or not isinstance(entry.get("path"), str):
            continue
        day = date.fromisoformat(entry["day"])
        path = (root / entry["path"]).resolve()
        if start <= day <= end and path.is_relative_to(root) and path.is_file():
            result.append(str(path))
    return result


def _tick_rows(connection: duckdb.DuckDBPyConnection, paths: list[str], start_ms: int, end_ms: int) -> Iterator[tuple[int, float, float]]:
    cursor = connection.execute("SELECT timestamp_ms,bid,ask FROM read_parquet(?) WHERE timestamp_ms >= ? AND timestamp_ms < ? ORDER BY timestamp_ms", [paths, start_ms, end_ms])
    while batch := cursor.fetchmany(25_000):
        yield from batch


def replay_latest(history: GoldHistory, days: int = 1, max_signals: int = 500) -> ReplayResult:
    if not 1 <= days <= 7:
        raise DatasetError("O replay interativo aceita entre 1 e 7 dias.")
    version, manifest = history.manifest()
    end_day = date.fromisoformat(str(manifest["coverage_end"]))
    start_day = end_day - timedelta(days=days - 1)
    warmup_day = start_day - timedelta(days=7)
    ticks = _paths(history.root, manifest.get("partitions"), start_day, end_day)
    aggregations = manifest.get("aggregations", {})
    candles = _paths(history.root, aggregations.get("5m", []) if isinstance(aggregations, dict) else [], warmup_day, end_day)
    if not ticks or not candles:
        raise DatasetError("A release não possui ticks e candles M5 para o período solicitado.")
    start_at = datetime.combine(start_day, time.min, tzinfo=timezone.utc)
    end_at = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=timezone.utc)
    start_ms, end_ms = int(start_at.timestamp() * 1000), int(end_at.timestamp() * 1000)
    connection = duckdb.connect(":memory:")
    try:
        candle_rows = connection.execute(
            "SELECT t,o,h,l,c,coalesce(bid_volume,0)+coalesce(ask_volume,0) FROM read_parquet(?) WHERE t >= ? AND t < ? ORDER BY t",
            [candles, int(datetime.combine(warmup_day, time.min, tzinfo=timezone.utc).timestamp() * 1000), end_ms],
        ).fetchall()
        completed = deque(maxlen=1000)
        candle_index = 0
        pipeline = ResearchPipeline()
        signals: list[dict[str, object]] = []
        ticks_evaluated = 0
        last_key: tuple[str, float] | None = None
        tick_window: deque[TickQuote] = deque()
        active_bar: datetime | None = None
        pivot_high: float | None = None
        pivot_low: float | None = None
        previous_close: float | None = None
        for timestamp_ms, bid, ask in _tick_rows(connection, ticks, start_ms, end_ms):
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
            tick_window.append(TickQuote(timestamp, float(bid), float(ask)))
            cutoff = timestamp - timedelta(seconds=900)
            while tick_window and tick_window[0].timestamp_utc < cutoff:
                tick_window.popleft()
            while candle_index < len(candle_rows) and candle_rows[candle_index][0] + 300_000 <= timestamp_ms:
                row = candle_rows[candle_index]
                completed.append(Candle(datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc), *map(float, row[1:])))
                candle_index += 1
            current_start = timestamp.replace(minute=timestamp.minute - timestamp.minute % 5, second=0, microsecond=0)
            ticks_evaluated += 1
            if current_start != active_bar:
                active_bar = current_start
                last_key = None
                if len(completed) >= 42:
                    m30 = aggregate_completed_candles(tuple(completed), 30, timestamp)
                    pivot_high, pivot_low = latest_confirmed_zigzag_levels(m30)
                    previous_close = completed[-1].close
            if len(completed) < 42 or previous_close is None:
                continue
            possible_buy = pivot_high is not None and previous_close <= pivot_high < float(ask)
            possible_sell = pivot_low is not None and previous_close >= pivot_low > float(bid)
            if not possible_buy and not possible_sell:
                continue
            if possible_buy and possible_sell:
                possible_buy = float(ask) - float(pivot_high) >= float(pivot_low) - float(bid)
                possible_sell = not possible_buy
            prospective_key = ("buy", float(pivot_high)) if possible_buy else ("sell", float(pivot_low))
            if prospective_key == last_key:
                continue
            mid = (float(bid) + float(ask)) / 2
            current = Candle(current_start, mid, mid, mid, mid)
            snapshot = MarketSnapshot(timestamp, "XAUUSD", float(bid), float(ask), 0.01, tuple(completed) + (current,), tuple(tick_window))
            decision = pipeline.evaluate(snapshot)
            if decision.candidate:
                level = float(decision.candidate.metadata["breakout_level"])
                key = (decision.candidate.side.value, level)
                if key != last_key and len(signals) < max_signals:
                    signals.append(decision.as_dict())
                last_key = key
        return ReplayResult(version, start_day.isoformat(), end_day.isoformat(), ticks_evaluated, signals)
    finally:
        connection.close()

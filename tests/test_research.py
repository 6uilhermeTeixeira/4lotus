from datetime import datetime, timedelta, timezone

from lotus_app.research.contracts import Candle, MarketSnapshot, Side, SignalCandidate, TickQuote
from lotus_app.research.experiments import ExperimentStore
from lotus_app.research.pipeline import ResearchPipeline
from lotus_app.research.zigzag_v1 import SOURCE, evaluate
from lotus_app.research.zigzag_v13 import evaluate as evaluate_v13


def breakout_snapshot(month: int = 7) -> MarketSnapshot:
    timestamp = datetime(2026, month, 20, 10, 0, tzinfo=timezone.utc)
    candles: list[Candle] = []
    bucket_highs = [101.0, 102.0, 106.0, 103.0, 102.0, 101.5, 102.5]
    bucket_lows = [99.0, 99.5, 100.0, 99.8, 99.6, 99.4, 99.7]
    start = timestamp - timedelta(hours=3, minutes=30)
    for bucket, (high, low) in enumerate(zip(bucket_highs, bucket_lows)):
        for row in range(6):
            close = 100.5 + bucket * 0.05 + row * 0.01
            candles.append(Candle(start + timedelta(minutes=bucket * 30 + row * 5), close - 0.02, high if row == 2 else close + 0.1, low if row == 3 else close - 0.1, close, 100))
    candles[-1] = Candle(candles[-1].timestamp_utc, candles[-1].open, candles[-1].high, candles[-1].low, 105.8, 100)
    candles.append(Candle(timestamp, 105.8, 106.2, 105.7, 106.1, 120))
    return MarketSnapshot(timestamp + timedelta(minutes=5), "XAUUSD", 106.1, 106.2, 0.01, tuple(candles))


def test_frozen_v1_matches_reference_geometry() -> None:
    candidate = evaluate(breakout_snapshot())
    assert candidate is not None
    assert candidate.side is Side.BUY
    assert candidate.entry == 106.2
    assert round(candidate.entry - candidate.stop, 8) == 2.4
    assert round(candidate.target - candidate.entry, 8) == 10.0
    assert candidate.stop_points == 240
    assert candidate.target_points == 1000
    assert candidate.metadata["source"] == SOURCE


def test_pipeline_routes_by_utc_month_and_keeps_neutral_layers() -> None:
    decision = ResearchPipeline().evaluate(breakout_snapshot(month=11))
    assert decision.action == "buy"
    assert [route.selected_id for route in decision.routes] == ["trigger.g01", "context.pass-through", "temporal.month.11"]
    assert all(item.allowed for item in decision.filters)


def test_v13_requires_causal_aligned_900_second_impulse() -> None:
    snapshot = breakout_snapshot()
    ticks = tuple(TickQuote(snapshot.timestamp_utc - timedelta(seconds=900 - index * 60), 97.95 + index * (8.1 / 15), 98.05 + index * (8.1 / 15)) for index in range(16))
    enriched = MarketSnapshot(snapshot.timestamp_utc, snapshot.symbol, snapshot.bid, snapshot.ask, snapshot.point_size, snapshot.candles, ticks)
    candidate = evaluate_v13(enriched)
    assert candidate is not None
    assert candidate.component_id == "trigger.g02"
    assert candidate.metadata["impulse_window_seconds"] == 900
    assert candidate.metadata["impulse_aligned_points"] >= 800
    assert ResearchPipeline().evaluate(enriched).routes[0].selected_id == "trigger.g02"


def test_v13_stays_silent_without_enough_impulse() -> None:
    snapshot = breakout_snapshot()
    ticks = tuple(TickQuote(snapshot.timestamp_utc - timedelta(seconds=900 - index * 60), 104.0 + index * 0.02, 104.1 + index * 0.02) for index in range(16))
    enriched = MarketSnapshot(snapshot.timestamp_utc, snapshot.symbol, snapshot.bid, snapshot.ask, snapshot.point_size, snapshot.candles, ticks)
    assert evaluate_v13(enriched) is None


def test_router_does_not_fallback_when_selected_trigger_has_no_signal() -> None:
    calls: list[str] = []

    def no_signal(snapshot: MarketSnapshot) -> None:
        calls.append("first")
        return None

    def alternate(snapshot: MarketSnapshot) -> SignalCandidate:
        calls.append("alternate")
        return SignalCandidate("trigger.g02", Side.BUY, 1, 0, 2, 1, 1, snapshot.timestamp_utc)

    decision = ResearchPipeline({"trigger.g01": no_signal, "trigger.g02": alternate}).evaluate(breakout_snapshot())
    assert decision.action == "hold"
    assert decision.reason == "selected_trigger_no_signal"
    assert calls == ["first"]


def test_experiment_store_writes_immutable_run_manifest(tmp_path) -> None:
    store = ExperimentStore(tmp_path)
    run = store.save({"dataset_version": "release-1", "start": "2026-01-01", "end": "2026-01-01", "ticks_evaluated": 10, "signal_count": 2, "metrics": {"buy_signals": 1}})
    path = tmp_path / f"{run['id']}.json"
    original = path.read_text(encoding="utf-8")
    store.save({"dataset_version": "release-1", "start": "2026-01-01", "end": "2026-01-01", "ticks_evaluated": 10, "signal_count": 2, "metrics": {"buy_signals": 1}})
    assert path.read_text(encoding="utf-8") == original
    assert store.list()[0]["dataset_version"] == "release-1"
    assert store.list()[0]["split"] == "exploratory"

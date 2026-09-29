"""Second trigger: V1 structural breakout confirmed by a causal tick impulse."""

from __future__ import annotations

from datetime import timedelta

from .contracts import MarketSnapshot, SignalCandidate
from .zigzag_v1 import COMPONENT_ID as BASE_COMPONENT_ID, evaluate as evaluate_v1


COMPONENT_ID = "trigger.g02"
IMPULSE_WINDOW_SECONDS = 900
IMPULSE_THRESHOLD_POINTS = 800.0


def aligned_impulse_points(snapshot: MarketSnapshot, direction: int) -> float | None:
    if not snapshot.ticks:
        return None
    current = snapshot.ticks[-1]
    cutoff = current.timestamp_utc - timedelta(seconds=IMPULSE_WINDOW_SECONDS)
    window = [tick for tick in snapshot.ticks if cutoff <= tick.timestamp_utc <= current.timestamp_utc]
    if len(window) < 2 or (current.timestamp_utc - window[0].timestamp_utc).total_seconds() < IMPULSE_WINDOW_SECONDS * 0.8:
        return None
    start_mid = (window[0].bid + window[0].ask) / 2
    current_mid = (current.bid + current.ask) / 2
    return direction * (current_mid - start_mid) / snapshot.point_size


def evaluate(snapshot: MarketSnapshot) -> SignalCandidate | None:
    base = evaluate_v1(snapshot)
    if base is None:
        return None
    direction = 1 if base.side.value == "buy" else -1
    impulse_points = aligned_impulse_points(snapshot, direction)
    if impulse_points is None or impulse_points < IMPULSE_THRESHOLD_POINTS:
        return None
    metadata = dict(base.metadata)
    metadata.update(
        {
            "setup_type": "happy_gold_zigzag_structural_tick",
            "impulse_window_seconds": IMPULSE_WINDOW_SECONDS,
            "impulse_threshold_points": IMPULSE_THRESHOLD_POINTS,
            "impulse_aligned_points": round(impulse_points, 6),
            "base_trigger": BASE_COMPONENT_ID,
            "source": "2Lotus@2e5a0fa:zigzag_scalper_v2_shadow",
        }
    )
    return SignalCandidate(
        COMPONENT_ID,
        base.side,
        base.entry,
        base.stop,
        base.target,
        base.stop_points,
        base.target_points,
        base.valid_until,
        metadata,
    )

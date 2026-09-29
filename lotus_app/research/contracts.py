from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class Candle:
    timestamp_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True, slots=True)
class TickQuote:
    timestamp_utc: datetime
    bid: float
    ask: float


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    timestamp_utc: datetime
    symbol: str
    bid: float
    ask: float
    point_size: float
    candles: tuple[Candle, ...]
    ticks: tuple[TickQuote, ...] = ()


@dataclass(frozen=True, slots=True)
class SignalCandidate:
    component_id: str
    side: Side
    entry: float
    stop: float
    target: float
    stop_points: float
    target_points: float
    valid_until: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FilterDecision:
    component_id: str
    allowed: bool
    reason: str
    observations: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RouteDecision:
    router_id: str
    selected_id: str
    reason: str
    observations: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResearchDecision:
    timestamp_utc: datetime
    action: str
    reason: str
    routes: tuple[RouteDecision, ...]
    filters: tuple[FilterDecision, ...]
    candidate: SignalCandidate | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp_utc"] = self.timestamp_utc.isoformat()
        if self.candidate:
            payload["candidate"]["side"] = self.candidate.side.value
            payload["candidate"]["valid_until"] = self.candidate.valid_until.isoformat()
        return payload

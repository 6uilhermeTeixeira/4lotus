from __future__ import annotations

from collections.abc import Callable

from .contracts import FilterDecision, MarketSnapshot, ResearchDecision, RouteDecision, SignalCandidate
from .zigzag_v1 import COMPONENT_ID, evaluate as evaluate_zigzag_v1
from .zigzag_v13 import COMPONENT_ID as IMPULSE_COMPONENT_ID, aligned_impulse_points, evaluate as evaluate_zigzag_v13


Trigger = Callable[[MarketSnapshot], SignalCandidate | None]


class ResearchPipeline:
    """One-branch causal pipeline. Routers never retry an alternate branch."""

    def __init__(self, triggers: dict[str, Trigger] | None = None) -> None:
        self.triggers = triggers or {COMPONENT_ID: evaluate_zigzag_v1, IMPULSE_COMPONENT_ID: evaluate_zigzag_v13}

    def evaluate(self, snapshot: MarketSnapshot) -> ResearchDecision:
        trigger_id = next(iter(self.triggers))
        route_observations: dict[str, object] = {"eligible": len(self.triggers)}
        if set(self.triggers) == {COMPONENT_ID, IMPULSE_COMPONENT_ID}:
            base = evaluate_zigzag_v1(snapshot)
            impulse = None if base is None else aligned_impulse_points(snapshot, 1 if base.side.value == "buy" else -1)
            if impulse is not None and impulse >= 800.0:
                trigger_id = IMPULSE_COMPONENT_ID
            route_observations.update({"impulse_900s_points": impulse, "threshold_points": 800.0})
            route_reason = "causal_900s_impulse_route" if trigger_id == IMPULSE_COMPONENT_ID else "causal_baseline_route"
        else:
            route_reason = "single_eligible_branch"
        routes = [RouteDecision("router.trigger.v1", trigger_id, route_reason, route_observations)]
        candidate = self.triggers[trigger_id](snapshot)
        if candidate is None:
            return ResearchDecision(snapshot.timestamp_utc, "hold", "selected_trigger_no_signal", tuple(routes), ())

        routes.append(RouteDecision("router.context.v1", "context.pass-through", "no_context_filter_registered"))
        context = FilterDecision("context.pass-through", True, "neutral_pass_through")
        month_id = f"temporal.month.{snapshot.timestamp_utc.month:02d}"
        routes.append(RouteDecision("router.temporal.v1", month_id, "utc_month_lookup", {"month": snapshot.timestamp_utc.month, "registered": False}))
        temporal = FilterDecision(month_id, True, "unregistered_month_pass_through")
        return ResearchDecision(snapshot.timestamp_utc, candidate.side.value, "candidate_approved", tuple(routes), (context, temporal), candidate)

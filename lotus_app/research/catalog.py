from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


ComponentKind = Literal["trigger", "context", "temporal", "router"]
ComponentStatus = Literal["empty", "draft", "validating", "validated", "frozen", "retired"]


@dataclass(frozen=True, slots=True)
class ComponentDefinition:
    id: str
    name: str
    kind: ComponentKind
    status: ComponentStatus
    version: str
    hypothesis: str
    origin: str | None = None


TRIGGER_SLOTS = tuple(f"trigger.g{index:02d}" for index in range(1, 5))
CONTEXT_SLOTS = tuple(f"context.c{index:02d}" for index in range(1, 9))
TEMPORAL_SLOTS = tuple(f"temporal.month.{index:02d}" for index in range(1, 13))

CATALOG = (
    ComponentDefinition(
        id="trigger.g01",
        name="ZigZag Scalper V1.0",
        kind="trigger",
        status="frozen",
        version="1.0.0",
        hypothesis="Rompimentos de pivôs M30 confirmados geram entradas direcionais em ticks.",
        origin="2Lotus@2e5a0fa:happy_gold_zigzag_scalper",
    ),
    ComponentDefinition(
        id="trigger.g02",
        name="ZigZag Scalper V1.3 · impulso de ticks",
        kind="trigger",
        status="validating",
        version="1.0.0",
        hypothesis="Um rompimento M30 acompanhado por deslocamento direcional de 900 segundos seleciona expansões mais fortes.",
        origin="2Lotus@2e5a0fa:zigzag_scalper_v2_shadow",
    ),
    ComponentDefinition("router.trigger.v1", "Roteador de gatilho", "router", "frozen", "1.0.0", "Seleciona um único gatilho elegível antes da avaliação."),
    ComponentDefinition("router.context.v1", "Roteador de contexto", "router", "draft", "1.0.0", "Mantém passagem neutra até existir um filtro contextual elegível."),
    ComponentDefinition("router.temporal.v1", "Roteador temporal", "router", "draft", "1.0.0", "Seleciona a política do mês UTC sem avaliar meses alternativos."),
)


def catalog_payload() -> dict[str, object]:
    registered = {item.id: asdict(item) for item in CATALOG}
    groups = {
        "trigger": [registered.get(slot, {"id": slot, "status": "empty"}) for slot in TRIGGER_SLOTS],
        "context": [registered.get(slot, {"id": slot, "status": "empty"}) for slot in CONTEXT_SLOTS],
        "temporal": [registered.get(slot, {"id": slot, "status": "empty", "month": index}) for index, slot in enumerate(TEMPORAL_SLOTS, 1)],
        "router": [asdict(item) for item in CATALOG if item.kind == "router"],
    }
    return {"capacities": {"trigger": 4, "context": 8, "temporal": 12, "router": 3}, "groups": groups}

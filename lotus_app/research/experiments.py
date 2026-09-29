from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


class ExperimentStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        recorded = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "kind": "tick_replay",
            "split": "exploratory",
            "component_versions": {"trigger.g01": "1.0.0", "trigger.g02": "1.0.0", "router.trigger.v1": "1.0.0", "router.context.v1": "1.0.0", "router.temporal.v1": "1.0.0"},
            **payload,
        }
        identity = json.dumps({key: value for key, value in recorded.items() if key != "created_at"}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        run_id = f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{sha256(identity.encode()).hexdigest()[:10]}"
        recorded["id"] = run_id
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self.root / f"{run_id}.json"
        if not destination.exists():
            temporary = destination.with_suffix(".tmp")
            temporary.write_text(json.dumps(recorded, indent=2, sort_keys=True, ensure_ascii=True), encoding="utf-8")
            temporary.replace(destination)
        return recorded

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.root.is_dir():
            return []
        results: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("run-*.json"), reverse=True)[:limit]:
            payload = json.loads(path.read_text(encoding="utf-8"))
            results.append({key: payload.get(key) for key in ("id", "created_at", "kind", "split", "dataset_version", "start", "end", "ticks_evaluated", "signal_count", "metrics")})
        return results

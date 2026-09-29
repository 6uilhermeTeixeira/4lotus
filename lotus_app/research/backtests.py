"""Read-only adapter for backtest snapshots produced by 2Lotus."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path


class BacktestError(RuntimeError):
    pass


IMPORTED_BACKTESTS = {
    "trigger.g01": {
        "name": "ZigZag Scalper V1.0",
        "source_id": "core-zigzag",
        "source_project": "2Lotus",
    },
}
SUPPORTED_PERIODS = (365, 1095, 1826, 2557)


class BacktestLibrary:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def _path(self, strategy_id: str, days: int) -> Path:
        if strategy_id not in IMPORTED_BACKTESTS:
            raise BacktestError("A estratégia ainda não possui backtest importado.")
        if days not in SUPPORTED_PERIODS:
            raise BacktestError("Período de backtest não suportado.")
        path = self.root / f"{IMPORTED_BACKTESTS[strategy_id]['source_id']}-{days}.json"
        if not path.is_file():
            raise BacktestError(f"O snapshot de {days} dias ainda não foi gerado no 2Lotus.")
        return path

    def read(self, strategy_id: str, days: int) -> dict[str, object]:
        path = self._path(strategy_id, days)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise BacktestError("O snapshot de backtest não pôde ser lido.") from error
        daily = payload.get("daily_pnl")
        if not isinstance(daily, list) or not isinstance(payload.get("summary"), dict):
            raise BacktestError("O snapshot não contém uma série de patrimônio válida.")
        balance = 10_000.0
        equity: list[dict[str, object]] = []
        for row in daily:
            if not isinstance(row, dict) or not isinstance(row.get("day"), str):
                continue
            try:
                day = date.fromisoformat(row["day"])
                pnl = float(row.get("net_pnl", 0.0))
            except (TypeError, ValueError):
                continue
            balance += pnl
            equity.append({"day": day.isoformat(), "net_pnl": round(pnl, 2), "equity": round(balance, 2)})
        return {
            "strategy_id": strategy_id,
            "strategy_name": IMPORTED_BACKTESTS[strategy_id]["name"],
            "source_project": IMPORTED_BACKTESTS[strategy_id]["source_project"],
            "source_file": path.name,
            "period_days": days,
            "period_start_utc": payload.get("period_start_utc"),
            "period_end_utc": payload.get("period_end_utc"),
            "summary": payload["summary"],
            "candidates_detected": payload.get("candidates_detected", 0),
            "candidates_eligible": payload.get("candidates_eligible", 0),
            "validation_status": payload.get("validation_status", "unknown"),
            "equity": equity,
        }

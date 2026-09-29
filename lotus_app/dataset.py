"""Read the immutable XAUUSD release without coupling to strategy code."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path

import duckdb


class DatasetError(RuntimeError):
    pass


class GoldHistory:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def manifest(self) -> tuple[str, dict[str, object]]:
        current = self.root / "releases" / "CURRENT"
        if not current.is_file():
            raise DatasetError("A release atual do histórico não está disponível.")
        version = current.read_text(encoding="utf-8").strip()
        if not version or "/" in version or ".." in version:
            raise DatasetError("O ponteiro da release é inválido.")
        manifest_path = self.root / "releases" / version / "manifest.json"
        if not manifest_path.is_file():
            raise DatasetError("O manifesto da release atual não está disponível.")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if payload.get("dataset_version") != version or payload.get("instrument") != "XAUUSD":
            raise DatasetError("A release atual não é um dataset XAUUSD válido.")
        return version, payload

    def summary(self) -> dict[str, object]:
        version, manifest = self.manifest()
        collection = manifest.get("collection", {})
        return {
            "version": version,
            "coverage_start": manifest.get("coverage_start"),
            "coverage_end": manifest.get("coverage_end"),
            "ticks": manifest.get("ticks", 0),
            "partitions": len(manifest.get("partitions", [])),
            "collection_status": collection.get("status", "unknown") if isinstance(collection, dict) else "unknown",
            "resolutions": sorted(manifest.get("aggregations", {}).keys()),
        }

    def candles(self, resolution: str, days: int) -> list[dict[str, float | int]]:
        if resolution not in {"1m", "5m", "1h", "1d"}:
            raise DatasetError("Resolução não suportada.")
        if not 1 <= days <= 2557:
            raise DatasetError("O período deve estar entre 1 e 2557 dias.")
        _, manifest = self.manifest()
        coverage_end = manifest.get("coverage_end")
        aggregations = manifest.get("aggregations", {})
        if not isinstance(coverage_end, str) or not isinstance(aggregations, dict):
            raise DatasetError("A release não contém agregações válidas.")
        cutoff = date.fromisoformat(coverage_end) - timedelta(days=days - 1)
        entries = aggregations.get(resolution, [])
        paths: list[str] = []
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                continue
            entry_day = entry.get("day")
            if not isinstance(entry_day, str) or date.fromisoformat(entry_day) < cutoff:
                continue
            path = (self.root / entry["path"]).resolve()
            if path.is_relative_to(self.root) and path.is_file():
                paths.append(str(path))
        if not paths:
            return []
        cutoff_ms = int(datetime.combine(cutoff, time.min, tzinfo=timezone.utc).timestamp() * 1000)
        limit = 3_000 if resolution == "1d" else 1_500
        connection = duckdb.connect(":memory:")
        try:
            rows = connection.execute(
                """SELECT t,o,h,l,c FROM (
                       SELECT t,o,h,l,c FROM read_parquet(?) WHERE t >= ? ORDER BY t DESC LIMIT ?
                   ) selected ORDER BY t""",
                [paths, cutoff_ms, limit],
            ).fetchall()
        finally:
            connection.close()
        return [{"time": int(row[0]), "open": float(row[1]), "high": float(row[2]), "low": float(row[3]), "close": float(row[4])} for row in rows]

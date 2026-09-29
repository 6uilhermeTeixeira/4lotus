from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def canonical_digest(payload: dict[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("sha256", None)
    raw = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    files: list[dict[str, str]] = []
    for path in sorted((ROOT / "bundles").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("sha256") != canonical_digest(payload):
            raise SystemExit(f"invalid bundle digest: {path.name}")
        files.append({"path": f"strategies/{path.name}", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    if not files:
        raise SystemExit("no strategy bundles found")
    commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    manifest = {
        "schema_version": "1.0",
        "source_repository": "6uilhermeTeixeira/4lotus",
        "source_commit": commit,
        "required_runner": "2lotus-runner>=0.1.0",
        "built_at_utc": datetime.now(UTC).isoformat(),
        "files": files,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        for item in files:
            archive.write(ROOT / "bundles" / Path(item["path"]).name, item["path"])


if __name__ == "__main__":
    main()


from fastapi.testclient import TestClient

from lotus_app.main import app


def test_health_and_bundle_catalog() -> None:
    client = TestClient(app)

    assert client.get("/health").json() == {"status": "ok", "service": "4lotus-strategy"}
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert "zigzag-v2.json" in ready.json()["bundles"]
    bundles = client.get("/api/bundles").json()["items"]
    assert {item["id"] for item in bundles} >= {"zigzag-scalper-v2", "zigzag-v7"}

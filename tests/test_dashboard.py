from fastapi.testclient import TestClient

from lotus_app.main import app


def test_navigation_starts_with_gold_history_and_has_no_operations() -> None:
    response = TestClient(app).get("/")
    assert response.status_code == 200
    html = response.text
    assert html.index("Histórico do ouro") < html.index("Estratégias")
    assert "Saúde operacional" not in html
    assert 'data-value="1826">5A' in html
    assert 'data-value="2557">7A' in html


def test_strategy_workbench_loads_frozen_baseline_without_importing_runtime() -> None:
    client = TestClient(app)
    html = client.get("/strategies").text
    assert "ZigZag Scalper V1.0" in html
    assert "Gatilhos <span id=\"trigger-tab-count\">2/4" in html
    assert "Contextos <span id=\"context-tab-count\">0/8" in html
    catalog = client.get("/api/strategies/catalog").json()
    assert catalog["capacities"] == {"trigger": 4, "context": 8, "temporal": 12, "router": 3}
    assert catalog["groups"]["trigger"][0]["status"] == "frozen"
    assert catalog["groups"]["trigger"][1]["status"] == "validating"
    assert catalog["groups"]["trigger"][2]["status"] == "empty"
    assert "A referência V1.0 é o único gatilho registrado" in client.get("/compare").text


def test_strategy_backtest_chart_loads_five_and_seven_year_snapshots() -> None:
    client = TestClient(app)
    for days, label in ((1826, "5 anos"), (2557, "7 anos")):
        response = client.get(f"/api/strategies/backtest?strategy_id=trigger.g01&days={days}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["source_project"] == "2Lotus"
        assert payload["period_days"] == days
        assert payload["equity"]
        assert payload["summary"]["trades_count"] > 0
    html = client.get("/strategies").text
    assert 'data-days="1826">5A' in html
    assert 'data-days="2557">7A' in html
    assert "backtest-chart" in html

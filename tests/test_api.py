import pytest
from fastapi.testclient import TestClient

from api import app
from tests.conftest import _DATA, TOTAL_ROWS, SOUTH_ROWS

client = TestClient(app)


# ── Meta endpoints ────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_root_redirects():
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (301, 302, 307, 308)


def test_datasets_returns_list():
    r = client.get("/datasets")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── /query — happy paths ──────────────────────────────────────────────────────

def test_query_load_and_filter(csv_path):
    r = client.post("/query", json={
        "pipeline": f"load {csv_path} | filter region = South"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["row_count"] == SOUTH_ROWS
    assert all(row["region"] == "South" for row in data["results"])


def test_query_returns_columns(csv_path):
    r = client.post("/query", json={
        "pipeline": f"load {csv_path} | select month, revenue"
    })
    assert r.json()["columns"] == ["month", "revenue"]


def test_query_plan_included(csv_path):
    r = client.post("/query", json={
        "pipeline": f"load {csv_path} | filter region = South | group by month | sum revenue"
    })
    plan = r.json()["plan"]
    assert len(plan) == 4
    assert plan[0]["operation"] == "LOAD"
    assert plan[1]["operation"] == "FILTER"
    assert plan[2]["operation"] == "GROUP BY"


def test_query_pipeline_steps_included(csv_path):
    r = client.post("/query", json={
        "pipeline": f"load {csv_path} | filter region = South"
    })
    steps = r.json()["pipeline_steps"]
    assert len(steps) == 2
    load_step = steps[0]
    assert load_step["operation"] == "LOAD"
    assert load_step["rows_before"] == 0
    assert load_step["rows_after"] == TOTAL_ROWS


def test_query_chart_returns_base64(csv_path):
    r = client.post("/query", json={
        "pipeline": (
            f"load {csv_path} | group by region | sum revenue | "
            "chart bar region revenue"
        )
    })
    assert r.status_code == 200
    chart = r.json()["chart"]
    assert chart is not None
    assert chart.startswith("data:image/png;base64,")


def test_query_no_chart_returns_null(csv_path):
    r = client.post("/query", json={
        "pipeline": f"load {csv_path} | filter region = South"
    })
    assert r.json()["chart"] is None


def test_query_scalar_aggregation(csv_path):
    r = client.post("/query", json={"pipeline": f"load {csv_path} | sum revenue"})
    data = r.json()
    assert "sum(revenue)" in data["scalars"]
    assert data["scalars"]["sum(revenue)"] == pytest.approx(1140.0)


def test_query_having(csv_path):
    r = client.post("/query", json={
        "pipeline": f"load {csv_path} | group by region | sum revenue | having revenue > 550"
    })
    assert r.status_code == 200
    assert all(row["revenue"] > 550 for row in r.json()["results"])


def test_query_elapsed_ms_positive(csv_path):
    r = client.post("/query", json={"pipeline": f"load {csv_path}"})
    assert r.json()["elapsed_ms"] > 0


def test_query_export(csv_path):
    # csv_path fixture already monkeypatches CWD to tmp_path, so relative path works
    r = client.post("/query", json={
        "pipeline": f"load {csv_path} | filter region = South | export exported.csv"
    })
    assert r.status_code == 200
    assert "exported.csv" in r.json()["exports"]


# ── /query — error handling ───────────────────────────────────────────────────

def test_query_parse_error_returns_422():
    r = client.post("/query", json={"pipeline": "filter region = South"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["stage"] == "parse"
    assert "message" in detail


def test_query_validation_error_returns_422(csv_path):
    r = client.post("/query", json={
        "pipeline": f"load {csv_path} | filter ghost_col = X"
    })
    assert r.status_code == 422
    assert r.json()["detail"]["stage"] == "validation"


def test_query_execution_error_returns_422():
    r = client.post("/query", json={"pipeline": "load nonexistent.csv"})
    assert r.status_code == 422
    assert r.json()["detail"]["stage"] in ("validation", "execution")


def test_query_parse_error_includes_column():
    r = client.post("/query", json={"pipeline": "load data.csv | chart scatter x y"})
    detail = r.json()["detail"]
    assert "column" in detail


# ── /query/upload ─────────────────────────────────────────────────────────────

def test_upload_csv_file():
    import pandas as pd
    csv_bytes = pd.DataFrame(_DATA).to_csv(index=False).encode()
    r = client.post(
        "/query/upload",
        data={"pipeline": "filter region = South | sort revenue desc"},
        files={"file": ("sales.csv", csv_bytes, "text/csv")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["row_count"] == SOUTH_ROWS


def test_upload_json_file():
    import pandas as pd
    json_bytes = pd.DataFrame(_DATA).to_json(orient="records").encode()
    r = client.post(
        "/query/upload",
        data={"pipeline": "sort revenue desc"},
        files={"file": ("data.json", json_bytes, "application/json")},
    )
    assert r.status_code == 200
    assert r.json()["row_count"] == TOTAL_ROWS


def test_upload_with_aggregation():
    import pandas as pd
    csv_bytes = pd.DataFrame(_DATA).to_csv(index=False).encode()
    r = client.post(
        "/query/upload",
        data={"pipeline": "group by region | sum revenue"},
        files={"file": ("sales.csv", csv_bytes, "text/csv")},
    )
    assert r.status_code == 200
    assert r.json()["row_count"] == 2  # South and North

"""End-to-end API tests with an isolated temp database."""
import io
import json
import os

import pytest

CSV = """date,region,units,revenue
2025-01-01,West,10,100.0
2025-01-02,West,20,250.0
2025-01-03,East,5,75.5
2025-01-04,East,15,180.0
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("INSIGHTBOARD_DB", str(tmp_path / "test.db"))
    import db
    import app as app_module

    db.init_db()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _upload(client):
    data = {"file": (io.BytesIO(CSV.encode()), "sales.csv")}
    return client.post("/upload", data=data, content_type="multipart/form-data")


def test_upload_and_dataset_page(client):
    resp = _upload(client)
    assert resp.status_code == 302  # redirect to the dataset page
    page = client.get("/datasets/1")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "region" in html and "revenue" in html
    assert "Chart builder" in html


def test_preview_bar_chart(client):
    _upload(client)
    resp = client.post(
        "/api/preview",
        json={"dataset_id": 1, "chart_type": "bar", "x_col": "region",
              "y_col": "revenue", "agg": "sum"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["labels"] == ["East", "West"]
    assert body["values"] == [255.5, 350.0]


def test_preview_count_agg(client):
    _upload(client)
    resp = client.post(
        "/api/preview",
        json={"dataset_id": 1, "chart_type": "bar", "x_col": "region", "agg": "count"},
    )
    assert resp.get_json()["values"] == [2, 2]


def test_preview_scatter(client):
    _upload(client)
    resp = client.post(
        "/api/preview",
        json={"dataset_id": 1, "chart_type": "scatter",
              "x_col": "units", "y_col": "revenue"},
    )
    body = resp.get_json()
    assert len(body["points"]) == 4
    assert body["points"][0] == {"x": 10.0, "y": 100.0}


def test_preview_bad_agg(client):
    _upload(client)
    resp = client.post(
        "/api/preview",
        json={"dataset_id": 1, "chart_type": "bar", "x_col": "region",
              "y_col": "revenue", "agg": "median"},
    )
    # was silently treated as sum before; an unknown agg is a client error
    assert resp.status_code == 400
    assert "median" in resp.get_json()["error"]


def test_preview_bad_column(client):
    _upload(client)
    resp = client.post(
        "/api/preview",
        json={"dataset_id": 1, "chart_type": "bar", "x_col": "nope", "agg": "count"},
    )
    assert resp.status_code == 400


def test_save_chart_and_dashboard_flow(client):
    _upload(client)
    # save a chart, creating a new dashboard inline
    resp = client.post(
        "/api/charts",
        json={"dataset_id": 1, "title": "Revenue by region", "chart_type": "bar",
              "x_col": "region", "y_col": "revenue", "agg": "sum",
              "new_dashboard_name": "My dashboard"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    dash_id, chart_id = body["dashboard_id"], body["chart_id"]

    # dashboard page renders the chart card
    page = client.get(f"/dashboards/{dash_id}")
    assert page.status_code == 200
    assert "Revenue by region" in page.get_data(as_text=True)

    # chart data endpoint serves the saved config
    data = client.get(f"/api/charts/{chart_id}/data").get_json()
    assert data["values"] == [255.5, 350.0]

    # delete the chart
    assert client.delete(f"/api/charts/{chart_id}").status_code == 200
    assert client.get(f"/api/charts/{chart_id}/data").status_code == 404


def test_delete_dataset(client):
    _upload(client)
    assert client.post("/datasets/1/delete").status_code == 302
    assert client.get("/datasets/1").status_code == 302  # gone -> redirect home


def test_reject_non_csv(client):
    data = {"file": (io.BytesIO(b"hello"), "notes.txt")}
    resp = client.post("/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 302
    # nothing was stored
    assert b"No datasets yet" in client.get("/").get_data()

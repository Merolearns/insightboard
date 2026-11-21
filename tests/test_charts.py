"""Unit tests for charts.compute_chart_data (no HTTP, no database)."""
import pandas as pd

from charts import compute_chart_data


def test_bar_chart_caps_high_cardinality_x():
    # 250 distinct X values: keep the 99 largest, lump the rest into "Other"
    df = pd.DataFrame(
        {"id": [f"row-{i}" for i in range(250)], "val": [1] * 250}
    )
    data = compute_chart_data(df, "bar", "id", "val", "sum")
    assert len(data["labels"]) == 100
    assert data["labels"][-1] == "Other"
    assert data["values"][-1] == 151  # 250 - 99
    assert sum(data["values"]) == 250  # nothing lost in the lump


def test_line_chart_caps_too():
    df = pd.DataFrame(
        {"id": [f"row-{i}" for i in range(150)], "val": [2] * 150}
    )
    data = compute_chart_data(df, "line", "id", "val", "sum")
    assert len(data["labels"]) == 100
    assert data["labels"][-1] == "Other"


def test_small_bar_chart_unchanged():
    df = pd.DataFrame({"region": ["East", "West"], "revenue": [10.0, 20.0]})
    data = compute_chart_data(df, "bar", "region", "revenue", "sum")
    assert data == {"labels": ["East", "West"], "values": [10.0, 20.0]}

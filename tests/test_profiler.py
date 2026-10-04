import pandas as pd

from profiler import infer_type, profile_dataframe


def _df():
    return pd.DataFrame(
        {
            "age": [25, 30, None, 41],
            "score": [88.5, 92.0, 76.25, None],
            "name": ["amy", "bo", "cy", "dee"],
            "joined": ["2024-01-15", "2024-02-01", "2024-03-10", "2024-04-20"],
            "active": [True, False, True, True],
        }
    )


def test_profile_shape():
    p = profile_dataframe(_df())
    assert p["rows"] == 4
    assert p["cols"] == 5
    assert len(p["columns"]) == 5
    assert p["duplicate_rows"] == 0


def test_type_inference():
    p = profile_dataframe(_df())
    by_name = {c["name"]: c["type"] for c in p["columns"]}
    # age has a None -> float64, still numeric
    assert by_name["age"] in ("integer", "float")
    assert by_name["score"] == "float"
    assert by_name["name"] == "string"
    assert by_name["joined"] == "datetime"
    assert by_name["active"] == "boolean"


def test_nulls_and_unique():
    p = profile_dataframe(_df())
    by_name = {c["name"]: c for c in p["columns"]}
    assert by_name["age"]["nulls"] == 1
    assert by_name["age"]["null_pct"] == 25.0
    assert by_name["name"]["unique"] == 4
    assert by_name["active"]["unique"] == 2


def test_numeric_stats():
    p = profile_dataframe(_df())
    by_name = {c["name"]: c for c in p["columns"]}
    stats = by_name["score"]["stats"]
    assert stats is not None
    assert stats["min"] == 76.25
    assert stats["max"] == 92.0
    assert stats["mean"] == round((88.5 + 92.0 + 76.25) / 3, 4)
    # strings get no stats
    assert by_name["name"]["stats"] is None


def test_samples_are_plain_values():
    p = profile_dataframe(_df())
    by_name = {c["name"]: c for c in p["columns"]}
    assert by_name["name"]["sample"] == ["amy", "bo", "cy", "dee"]
    assert len(by_name["age"]["sample"]) == 3  # None excluded


def test_infer_type_direct():
    assert infer_type(pd.Series([1, 2, 3])) == "integer"
    assert infer_type(pd.Series(["a", "b"])) == "string"
    assert infer_type(pd.Series(["2024-01-01", "2024-05-05"])) == "datetime"
    assert infer_type(pd.Series(["true", "False", "TRUE"])) == "boolean"


def test_duplicate_rows_counted():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    assert profile_dataframe(df)["duplicate_rows"] == 1

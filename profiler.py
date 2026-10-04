"""Data profiling for insightboard.

profile_dataframe(df) summarizes a pandas DataFrame into plain JSON-able
dicts: row/column counts plus per-column type, nulls, unique count, sample
values and numeric stats where they make sense.
"""
import math

import pandas as pd


def _clean(value):
    """Make a value safe for JSON (NaN/NaT/inf -> None)."""
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    # numpy scalars -> python scalars
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, TypeError):
            return str(value)
    return value


def infer_type(series):
    """Best-effort column type label: boolean/integer/float/datetime/string."""
    s = series.dropna()
    if pd.api.types.is_bool_dtype(series.dtype):
        return "boolean"
    if len(s) and s.astype(str).str.lower().isin(["true", "false"]).all():
        # string column holding true/false values
        return "boolean"
    if pd.api.types.is_integer_dtype(series.dtype):
        return "integer"
    if pd.api.types.is_float_dtype(series.dtype):
        return "float"
    if pd.api.types.is_datetime64_any_dtype(series.dtype):
        return "datetime"
    if len(s):
        # last resort: does it look like dates?
        parsed = pd.to_datetime(s.astype(str), errors="coerce", format="mixed")
        if parsed.notna().mean() >= 0.8:
            return "datetime"
    return "string"


def _numeric_stats(series):
    nums = pd.to_numeric(series, errors="coerce").dropna()
    if len(nums) == 0:
        return None
    desc = nums.describe()
    return {
        "min": _clean(round(float(desc["min"]), 4)),
        "max": _clean(round(float(desc["max"]), 4)),
        "mean": _clean(round(float(desc["mean"]), 4)),
        "median": _clean(round(float(desc["50%"]), 4)),
        "std": _clean(round(float(desc["std"]), 4)) if len(nums) > 1 else None,
    }


def profile_column(series):
    nulls = int(series.isna().sum())
    total = len(series)
    non_null = series.dropna()
    sample = [_clean(v) for v in non_null.head(5).tolist()]
    col_type = infer_type(series)
    stats = _numeric_stats(series) if col_type in ("integer", "float") else None
    return {
        "name": str(series.name),
        "type": col_type,
        "nulls": nulls,
        "null_pct": round(100.0 * nulls / total, 2) if total else 0.0,
        "unique": int(non_null.nunique()),
        "sample": sample,
        "stats": stats,
    }


def profile_dataframe(df):
    """Return the full profile dict for a DataFrame."""
    return {
        "rows": int(len(df)),
        "cols": int(len(df.columns)),
        "columns": [profile_column(df[c]) for c in df.columns],
        # duplicate rows is a cheap but useful data-quality signal
        "duplicate_rows": int(df.duplicated().sum()),
    }

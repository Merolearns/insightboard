"""Turn a DataFrame + chart config into Chart.js-ready data.

Bar/line/pie aggregate Y over X (sum/avg/count/min/max). Scatter just needs
two numeric columns and returns raw points (capped so huge datasets don't
freeze the browser).
"""
import pandas as pd

AGG_FUNCS = {
    "sum": "sum",
    "avg": "mean",
    "count": "count",
    "min": "min",
    "max": "max",
}

CHART_TYPES = ("bar", "line", "pie", "scatter")
MAX_SCATTER_POINTS = 500
MAX_PIE_SLICES = 12


def compute_chart_data(df, chart_type, x_col, y_col=None, agg="sum"):
    if chart_type not in CHART_TYPES:
        raise ValueError(f"unknown chart type: {chart_type}")
    if x_col not in df.columns:
        raise ValueError(f"unknown column: {x_col}")

    if chart_type == "scatter":
        return _scatter(df, x_col, y_col)
    return _aggregated(df, chart_type, x_col, y_col, agg)


def _scatter(df, x_col, y_col):
    if not y_col or y_col not in df.columns:
        raise ValueError("scatter charts need both an X and a Y column")
    sub = df[[x_col, y_col]].copy()
    sub[x_col] = pd.to_numeric(sub[x_col], errors="coerce")
    sub[y_col] = pd.to_numeric(sub[y_col], errors="coerce")
    sub = sub.dropna()
    if len(sub) > MAX_SCATTER_POINTS:
        # deterministic sample so the chart doesn't change on every load
        sub = sub.sample(MAX_SCATTER_POINTS, random_state=42).sort_index()
    points = [
        {"x": round(float(r[x_col]), 4), "y": round(float(r[y_col]), 4)}
        for _, r in sub.iterrows()
    ]
    return {"points": points}


def _aggregated(df, chart_type, x_col, y_col, agg):
    if agg == "count" or not y_col:
        grouped = df.groupby(x_col, dropna=False).size()
        labels = [str(v) for v in grouped.index]
        values = [int(v) for v in grouped.values]
    else:
        if y_col not in df.columns:
            raise ValueError(f"unknown column: {y_col}")
        func = AGG_FUNCS.get(agg, "sum")
        tmp = pd.DataFrame({"_x": df[x_col], "_y": pd.to_numeric(df[y_col], errors="coerce")})
        tmp = tmp.dropna(subset=["_y"])
        if tmp.empty:
            return {"labels": [], "values": []}
        grouped = tmp.groupby("_x", dropna=False)["_y"].agg(func)
        labels = [str(v) for v in grouped.index]
        values = [round(float(v), 4) for v in grouped.values]

    if chart_type == "pie" and len(labels) > MAX_PIE_SLICES:
        # keep the biggest slices, lump the rest into "Other"
        pairs = sorted(zip(labels, values), key=lambda p: p[1], reverse=True)
        keep = pairs[: MAX_PIE_SLICES - 1]
        other = round(sum(v for _, v in pairs[MAX_PIE_SLICES - 1 :]), 4)
        labels = [label for label, _ in keep] + ["Other"]
        values = [v for _, v in keep] + [other]

    return {"labels": labels, "values": values}

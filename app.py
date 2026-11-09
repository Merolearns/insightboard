"""insightboard — upload a CSV, get an interactive analytics dashboard."""
import os

import pandas as pd
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.utils import secure_filename

import db
from charts import CHART_TYPES, compute_chart_data
from profiler import profile_dataframe

app = Flask(__name__)
app.secret_key = os.environ.get("INSIGHTBOARD_SECRET", "dev-secret-change-me")

ALLOWED_EXTENSIONS = {"csv"}


def _load_dataset(dataset_id):
    """Return (dataset_row, dataframe) or (None, None)."""
    ds = db.get_dataset(dataset_id)
    if not ds:
        return None, None
    try:
        df = pd.read_csv(db.dataset_path(ds))
    except Exception:
        return ds, None
    return ds, df


def _read_upload(file_storage):
    """Parse an uploaded CSV into a DataFrame. Raises ValueError on failure."""
    try:
        return pd.read_csv(file_storage)
    except UnicodeDecodeError:
        file_storage.seek(0)
        try:
            return pd.read_csv(file_storage, encoding="latin1")
        except Exception as e:
            raise ValueError(f"could not parse CSV: {e}")
    except Exception as e:
        raise ValueError(f"could not parse CSV: {e}")


# --- pages ------------------------------------------------------------------

@app.route("/")
def index():
    return render_template(
        "index.html",
        datasets=db.list_datasets(),
        dashboards=db.list_dashboards(),
    )


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Pick a CSV file first.")
        return redirect(url_for("index"))
    if "." not in file.filename or file.filename.rsplit(".", 1)[1].lower() not in ALLOWED_EXTENSIONS:
        flash("Only .csv files are supported.")
        return redirect(url_for("index"))

    try:
        df = _read_upload(file)
    except ValueError as e:
        flash(str(e))
        return redirect(url_for("index"))
    if df.empty or len(df.columns) == 0:
        flash("That CSV looks empty — nothing to analyze.")
        return redirect(url_for("index"))

    name = os.path.splitext(secure_filename(file.filename))[0].replace("_", " ") or "untitled"
    dataset_id = db.create_dataset(name, "", len(df), len(df.columns))
    filename = f"{dataset_id}_{secure_filename(file.filename)}"
    df.to_csv(os.path.join(db.upload_dir(), filename), index=False)
    # two-step so the file on disk is namespaced by the dataset id
    db.set_dataset_filename(dataset_id, filename)

    flash(f"Uploaded {name} — {len(df)} rows, {len(df.columns)} columns.")
    return redirect(url_for("dataset_page", dataset_id=dataset_id))


@app.route("/datasets/<int:dataset_id>")
def dataset_page(dataset_id):
    ds, df = _load_dataset(dataset_id)
    if not ds:
        flash("Dataset not found.")
        return redirect(url_for("index"))
    if df is None:
        flash("Couldn't read that CSV back from disk.")
        return redirect(url_for("index"))
    profile = profile_dataframe(df)
    return render_template(
        "dataset.html",
        dataset=ds,
        profile=profile,
        chart_types=CHART_TYPES,
        dashboards=db.list_dashboards(),
    )


@app.route("/datasets/<int:dataset_id>/delete", methods=["POST"])
def delete_dataset(dataset_id):
    if not db.get_dataset(dataset_id):
        flash("Dataset not found.")
        return redirect(url_for("index"))
    db.delete_dataset(dataset_id)
    flash("Dataset deleted.")
    return redirect(url_for("index"))


@app.route("/dashboards")
def dashboards_page():
    return render_template("dashboards.html", dashboards=db.list_dashboards())


@app.route("/dashboards", methods=["POST"])
def create_dashboard():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Give the dashboard a name.")
        return redirect(url_for("dashboards_page"))
    dashboard_id = db.create_dashboard(name)
    return redirect(url_for("dashboard_page", dashboard_id=dashboard_id))


@app.route("/dashboards/<int:dashboard_id>")
def dashboard_page(dashboard_id):
    dash = db.get_dashboard(dashboard_id)
    if not dash:
        flash("Dashboard not found.")
        return redirect(url_for("dashboards_page"))
    return render_template(
        "dashboard.html", dashboard=dash, charts=db.list_charts(dashboard_id)
    )


@app.route("/dashboards/<int:dashboard_id>/delete", methods=["POST"])
def delete_dashboard(dashboard_id):
    db.delete_dashboard(dashboard_id)
    flash("Dashboard deleted.")
    return redirect(url_for("dashboards_page"))


# --- chart data API ----------------------------------------------------------

@app.route("/api/preview", methods=["POST"])
def api_preview():
    """Compute chart data for an unsaved chart config (chart builder preview)."""
    payload = request.get_json(force=True, silent=True) or {}
    try:
        dataset_id = int(payload.get("dataset_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "dataset_id is required"}), 400
    ds, df = _load_dataset(dataset_id)
    if df is None:
        return jsonify({"error": "dataset not found"}), 404
    try:
        data = compute_chart_data(
            df,
            payload.get("chart_type", "bar"),
            payload.get("x_col"),
            payload.get("y_col"),
            payload.get("agg", "sum"),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(data)


@app.route("/api/charts/<int:chart_id>/data")
def api_chart_data(chart_id):
    chart = db.get_chart(chart_id)
    if not chart:
        return jsonify({"error": "chart not found"}), 404
    ds, df = _load_dataset(chart["dataset_id"])
    if df is None:
        return jsonify({"error": "dataset not found"}), 404
    try:
        data = compute_chart_data(
            df, chart["chart_type"], chart["x_col"], chart["y_col"], chart["agg"] or "sum"
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(data)


@app.route("/api/charts", methods=["POST"])
def api_save_chart():
    """Save a chart to a dashboard. Pass dashboard_id or new_dashboard_name."""
    payload = request.get_json(force=True, silent=True) or {}
    title = (payload.get("title") or "Untitled chart").strip()
    chart_type = payload.get("chart_type", "bar")
    x_col = payload.get("x_col")
    y_col = payload.get("y_col")
    agg = payload.get("agg") or ("sum" if chart_type != "scatter" else None)
    try:
        dataset_id = int(payload.get("dataset_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "dataset_id is required"}), 400

    if chart_type not in CHART_TYPES or not x_col:
        return jsonify({"error": "chart_type and x_col are required"}), 400
    if not db.get_dataset(dataset_id):
        return jsonify({"error": "dataset not found"}), 404

    dashboard_id = payload.get("dashboard_id")
    if dashboard_id:
        try:
            dashboard_id = int(dashboard_id)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid dashboard_id"}), 400
        if not db.get_dashboard(dashboard_id):
            return jsonify({"error": "dashboard not found"}), 404
    else:
        name = (payload.get("new_dashboard_name") or "").strip()
        if not name:
            return jsonify({"error": "pick a dashboard or name a new one"}), 400
        dashboard_id = db.create_dashboard(name)

    chart_id = db.add_chart(
        dashboard_id, dataset_id, title, chart_type, x_col, y_col, agg
    )
    return jsonify({"chart_id": chart_id, "dashboard_id": dashboard_id})


@app.route("/api/charts/<int:chart_id>", methods=["DELETE"])
def api_delete_chart(chart_id):
    if not db.get_chart(chart_id):
        return jsonify({"error": "chart not found"}), 404
    db.delete_chart(chart_id)
    return jsonify({"ok": True})


if __name__ == "__main__":
    db.init_db()
    app.run(debug=True)

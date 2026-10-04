"""SQLite storage for insightboard.

Three tables: datasets (uploaded CSVs), dashboards (named collections),
charts (a chart config belongs to one dashboard and reads from one dataset).

DB location defaults to ./data/insightboard.db next to this file; tests
override it with the INSIGHTBOARD_DB env var, which is why db_path() reads
the env on every call instead of once at import.
"""
import os
import sqlite3
from datetime import datetime, timezone


def _default_db_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "data", "insightboard.db")


def db_path():
    return os.environ.get("INSIGHTBOARD_DB", _default_db_path())


def upload_dir():
    d = os.path.join(os.path.dirname(db_path()), "uploads")
    os.makedirs(d, exist_ok=True)
    return d


SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    filename TEXT NOT NULL,
    rows INTEGER NOT NULL,
    cols INTEGER NOT NULL,
    uploaded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dashboards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS charts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dashboard_id INTEGER NOT NULL REFERENCES dashboards(id) ON DELETE CASCADE,
    dataset_id INTEGER NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    chart_type TEXT NOT NULL,
    x_col TEXT NOT NULL,
    y_col TEXT,
    agg TEXT,
    created_at TEXT NOT NULL
);
"""


def _connect():
    path = db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = _connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _one(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


def _all(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


# --- datasets ---------------------------------------------------------------

def create_dataset(name, filename, rows, cols):
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO datasets (name, filename, rows, cols, uploaded_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (name, filename, rows, cols, _now()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_datasets():
    conn = _connect()
    try:
        return [dict(r) for r in _all(conn, "SELECT * FROM datasets ORDER BY id DESC")]
    finally:
        conn.close()


def get_dataset(dataset_id):
    conn = _connect()
    try:
        row = _one(conn, "SELECT * FROM datasets WHERE id = ?", (dataset_id,))
        return dict(row) if row else None
    finally:
        conn.close()


def dataset_path(dataset):
    return os.path.join(upload_dir(), dataset["filename"])


def set_dataset_filename(dataset_id, filename):
    conn = _connect()
    try:
        conn.execute(
            "UPDATE datasets SET filename = ? WHERE id = ?", (filename, dataset_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_dataset(dataset_id):
    ds = get_dataset(dataset_id)
    conn = _connect()
    try:
        conn.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
        conn.commit()
    finally:
        conn.close()
    # remove the stored csv too; charts referencing it go away via cascade
    if ds:
        try:
            os.remove(dataset_path(ds))
        except OSError:
            pass  # file already gone, not worth failing over


# --- dashboards -------------------------------------------------------------

def create_dashboard(name):
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO dashboards (name, created_at) VALUES (?, ?)",
            (name, _now()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_dashboards():
    conn = _connect()
    try:
        rows = _all(
            conn,
            """SELECT d.*, COUNT(c.id) AS chart_count FROM dashboards d
               LEFT JOIN charts c ON c.dashboard_id = d.id
               GROUP BY d.id ORDER BY d.id DESC""",
        )
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_dashboard(dashboard_id):
    conn = _connect()
    try:
        row = _one(conn, "SELECT * FROM dashboards WHERE id = ?", (dashboard_id,))
        return dict(row) if row else None
    finally:
        conn.close()


def delete_dashboard(dashboard_id):
    conn = _connect()
    try:
        conn.execute("DELETE FROM dashboards WHERE id = ?", (dashboard_id,))
        conn.commit()
    finally:
        conn.close()


# --- charts -----------------------------------------------------------------

def add_chart(dashboard_id, dataset_id, title, chart_type, x_col, y_col, agg):
    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO charts
               (dashboard_id, dataset_id, title, chart_type, x_col, y_col, agg, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (dashboard_id, dataset_id, title, chart_type, x_col, y_col, agg, _now()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_charts(dashboard_id):
    conn = _connect()
    try:
        rows = _all(
            conn,
            """SELECT c.*, d.name AS dataset_name FROM charts c
               JOIN datasets d ON d.id = c.dataset_id
               WHERE c.dashboard_id = ? ORDER BY c.id""",
            (dashboard_id,),
        )
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_chart(chart_id):
    conn = _connect()
    try:
        row = _one(conn, "SELECT * FROM charts WHERE id = ?", (chart_id,))
        return dict(row) if row else None
    finally:
        conn.close()


def delete_chart(chart_id):
    conn = _connect()
    try:
        conn.execute("DELETE FROM charts WHERE id = ?", (chart_id,))
        conn.commit()
    finally:
        conn.close()

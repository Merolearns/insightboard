# insightboard

A small full-stack web app for data analytics: upload a CSV, get an automatic
data profile, build charts with a point-and-click builder, and save them into
dashboards. I built it to practice putting the whole pipeline together —
file upload, pandas profiling, a JSON API, and Chart.js on the frontend —
instead of just doing analysis in a notebook.

Everything runs locally. No accounts, no cloud, no tracking.

## What it does

- **CSV upload** — drag & drop or file picker. Files are parsed with pandas
  and stored server-side (SQLite keeps the metadata).
- **Auto data profile** — every dataset gets row/column counts, per-column
  type inference (integer, float, boolean, datetime, string), null %,
  unique counts, sample values, and min/max/mean/median/std for numeric
  columns. Duplicate row count too.
- **Chart builder** — pick a dataset, chart type (bar, line, pie, scatter),
  X and Y columns, and an aggregation (sum, avg, count, min, max). Live
  preview before you commit. Pie charts collapse small slices into "Other";
  scatter plots cap at 500 points so big datasets don't freeze the browser.
- **Dashboards** — name a dashboard, save multiple charts to it, view them
  all on one page. Charts and dashboards persist in SQLite.
- **Dataset management** — list and delete datasets from the home page.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000. The database and uploaded CSVs live in
`data/` (gitignored) and are created on first run.

Try it with the included samples:

- `sample_data/sample_sales.csv` — 500 rows of fictional store sales
  (date, region, product, units, revenue)
- `sample_data/sample_traffic.csv` — ~1,000 rows of fictional website
  traffic (date, page, visits, signups, bounce_rate)

Both are randomly generated in-code, clearly fake, and just there so you
can click around without hunting for a CSV.

## Tests

```bash
pytest tests/ -q
```

15 tests: profiler unit tests (type inference, null handling, numeric
stats) and API end-to-end tests (upload → profile → preview → save chart
→ dashboard → delete) running against a temp database.

## Stack

Python, Flask, pandas, SQLite (stdlib `sqlite3`), Chart.js (CDN), vanilla
CSS/JS — no frontend framework. I kept the JS plain on purpose; the app
is small enough that a framework would just be overhead.

## Things I'd improve

- Chart.js is loaded from a CDN, so the chart pages need internet. Vendoring
  it would fix that.
- The profiler reads the whole CSV into memory — fine for the datasets I
  tested with, but chunked reading would be needed for really big files.
- No auth or multi-user support; it's a single-user local app by design.
- Date handling in charts is basic (dates are treated as categories on the
  X axis). A proper time-series mode with resampling would be a nice next
  step.

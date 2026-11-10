"""Strict SQL check for nl-hwc-report.

Runs every apply_sql_query in spec.yaml the way Ecoscope Desktop does, not
the way plain sqlite does:

  * the task's own validator (must start with SELECT, no mid-query `;`,
    10k char cap) -- copied verbatim from
    ecoscope/platform/tasks/transformation/_sql_query.py
  * the task's deny-by-default SQLite authorizer (function allowlist, may
    read only `df`, json_each, json_tree) -- also verbatim
  * the same data chain: events_prepared -> report_time parsed and moved to
    Africa/Nairobi -> split by month -> every per-month query on every month
  * then checks that each column a chart / table / KPI / colormap reads from
    a query's output actually exists in that output

The old dev/check_sql.py ran in plain sqlite with neither the validator nor
the authorizer, which is why the semicolon and WITH failures got through.

Needs only pandas + numpy + pyyaml (no geopandas / pandasql): geometry is
carried as WKT, which is what apply_sql_query converts it to anyway.

    python3 dev/check_sql_strict.py [--data path/to/events.json]

--data takes a JSON list of events shaped like process_events_details
output (event_details as a dict or JSON string); without it the synthetic
fixture builder is run in-process.
"""

import json
import re
import sqlite3
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = yaml.safe_load(open(ROOT / "spec.yaml"))
TZ = "Africa/Nairobi"

# --------------------------------------------------------------------------
# verbatim from _sql_query.py (ecoscope 2.28.0)
# --------------------------------------------------------------------------
MAX_QUERY_LENGTH = 10_000
ALLOWED_FUNCTIONS = frozenset(
    {
        "count",
        "sum",
        "total",
        "avg",
        "min",
        "max",
        "group_concat",
        "string_agg",
        "abs",
        "round",
        "coalesce",
        "ifnull",
        "nullif",
        "iif",
        "typeof",
        "lower",
        "upper",
        "length",
        "substr",
        "substring",
        "trim",
        "ltrim",
        "rtrim",
        "replace",
        "instr",
        "like",
        "glob",
        "printf",
        "format",
        "concat",
        "concat_ws",
        "ceil",
        "ceiling",
        "floor",
        "sqrt",
        "pow",
        "power",
        "exp",
        "ln",
        "log",
        "log10",
        "mod",
        "sign",
        "date",
        "time",
        "datetime",
        "julianday",
        "strftime",
        "unixepoch",
        "json",
        "json_extract",
        "json_array_length",
        "json_type",
        "json_valid",
        "json_array",
        "json_object",
        "json_group_array",
        "json_group_object",
        "row_number",
        "rank",
        "dense_rank",
        "percent_rank",
        "cume_dist",
        "ntile",
        "lag",
        "lead",
        "first_value",
        "last_value",
        "nth_value",
    }
)
_READABLE_TABLES = frozenset({"df", "json_each", "json_tree"})
_RECURSIVE = getattr(sqlite3, "SQLITE_RECURSIVE", 33)


def _authorizer(action, arg1, arg2, db_name, trigger):
    if action in (sqlite3.SQLITE_SELECT, _RECURSIVE):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_OK if arg1 in _READABLE_TABLES else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION:
        return (
            sqlite3.SQLITE_OK
            if arg2 and arg2.lower() in ALLOWED_FUNCTIONS
            else sqlite3.SQLITE_DENY
        )
    return sqlite3.SQLITE_DENY


def validate_sql_query(value: str) -> str:
    if not value or not value.strip():
        return value.strip()
    if len(value) > MAX_QUERY_LENGTH:
        raise ValueError(
            f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters"
        )
    q = value.strip()
    p = q.find(";")
    if p != -1 and p < len(q) - 1:
        raise ValueError("Multiple SQL statements are not allowed (no semicolons)")
    if not q.upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed")
    return q


def _jsonify(v):
    if isinstance(v, (np.ndarray, set, list, dict)):
        return json.dumps(
            list(v) if isinstance(v, set) else v, ensure_ascii=False, default=str
        )
    return v


def apply_sql_query(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """sanitize (complex -> JSON text) + validate + authorized sqlite run."""
    q = validate_sql_query(query)
    d = df.reset_index(drop=True).copy()
    for c in d.columns:
        s = d[c]
        if pd.api.types.is_datetime64_any_dtype(s):
            d[c] = s.astype(str).where(
                s.notna(), None
            )  # how SQLAlchemy writes tz-aware ts
        elif s.dtype == object:
            d[c] = s.map(_jsonify)
    con = sqlite3.connect(":memory:")
    try:
        d.to_sql("df", con, index=False)
        con.set_authorizer(_authorizer)
        return pd.read_sql_query(q, con)
    except Exception as e:  # mirror the task's wrapping
        raise ValueError(f"SQL query failed: {e}") from None
    finally:
        con.close()


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------
def fixture_events() -> pd.DataFrame:
    """Run dev/build_mock_io.py with geopandas/shapely stubbed."""
    captured = {}

    class Point:
        def __init__(self, x, y):
            self.wkt = f"POINT ({x} {y})"

    class GDF(pd.DataFrame):
        def __init__(self, data=None, geometry=None, crs=None, **kw):
            super().__init__(data, **kw)

        @property
        def _constructor(self):
            return GDF

        def to_parquet(self, path, index=False):
            captured[Path(path).name.split(".")[0]] = pd.DataFrame(self)

    gpd = types.ModuleType("geopandas")
    gpd.GeoDataFrame = GDF
    shp = types.ModuleType("shapely")
    geo = types.ModuleType("shapely.geometry")
    geo.Point = Point
    sys.modules.update({"geopandas": gpd, "shapely": shp, "shapely.geometry": geo})
    src = (ROOT / "dev/build_mock_io.py").read_text()
    exec(
        compile(src, "build_hwc_fixtures.py", "exec"),
        {"__name__": "fixtures", "__file__": str(ROOT / "dev/build_mock_io.py")},
    )
    ev = captured["events"]
    ev["geometry"] = ev["geometry"].map(lambda g: g.wkt if g is not None else None)
    return ev


def json_events(path: str) -> pd.DataFrame:
    ev = pd.DataFrame(json.load(open(path)))
    ev["time"] = pd.to_datetime(ev["time"], utc=True, format="ISO8601")
    return ev


# --------------------------------------------------------------------------
# spec helpers
# --------------------------------------------------------------------------
TASKS = {}


def _walk(x):
    if isinstance(x, dict):
        if "task" in x and "id" in x:
            TASKS[x["id"]] = x
        for v in x.values():
            _walk(v)
    elif isinstance(x, list):
        for v in x:
            _walk(v)


_walk(SPEC)
COL_KEYS = {
    "category",
    "column",
    "column_name",
    "value_column",
    "label_column",
    "input_column_name",
    "x_axis",
    "y_axis",
    "columns",
    "color_column",
    "tooltip_columns",
    "time_col",
}


def consumers(tid):
    pat = re.compile(r"workflow\.%s\.return" % re.escape(tid))
    return [k for k, v in TASKS.items() if pat.search(json.dumps(v))]


def column_refs(task):
    """Column names a task's partial reads (strings / lists under COL_KEYS)."""
    out = set()

    def rec(x, key=None):
        if isinstance(x, dict):
            for k, v in x.items():
                rec(v, k)
        elif isinstance(x, list):
            for v in x:
                rec(v, key)
        elif isinstance(x, str) and key in COL_KEYS and not x.startswith("${{"):
            out.add(x)

    rec(task.get("partial") or {})
    return out


def query(tid):
    return TASKS[tid]["partial"]["query"]


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------
def main():
    data = sys.argv[sys.argv.index("--data") + 1] if "--data" in sys.argv else None
    ev = json_events(data) if data else fixture_events()
    fails = 0

    def report(tid, ok, msg=""):
        nonlocal fails
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {tid:18s} {msg}")

    print(
        f"input: {len(ev)} events  ({'live data' if data else 'synthetic fixture'})\n"
    )

    # events_prepared on the whole frame
    prep = apply_sql_query(ev, query("events_prepared"))
    report(
        "events_prepared",
        True,
        f"{len(prep)} rows, {int(prep.is_conflict.sum())} conflict",
    )

    # extract_column_as_type -> convert_values_to_timezone -> month split
    prep["report_time"] = pd.to_datetime(
        prep["report_time"], utc=True, format="mixed"
    ).dt.tz_convert(TZ)
    bad_t = prep["report_time"].isna().sum()
    report(
        "report_time",
        bad_t == 0,
        f"{bad_t} rows failed to parse" if bad_t else "all parsed",
    )
    prep["_month"] = prep["report_time"].dt.strftime("%Y-%m")
    months = {m: g.drop(columns="_month") for m, g in prep.groupby("_month")}
    indexed = prep.drop(columns="_month")
    print(f"  months: {', '.join(f'{m} ({len(g)})' for m, g in months.items())}\n")

    outputs = {}
    for tid, t in TASKS.items():
        if t["task"] != "apply_sql_query" or tid == "events_prepared":
            continue
        src = json.dumps(t)
        frames = {"(all)": indexed} if "events_indexed.return" in src else months
        for m, g in frames.items():
            try:
                out = apply_sql_query(g, query(tid))
                outputs.setdefault(tid, out)
                if m == next(iter(frames)):
                    report(
                        tid,
                        True,
                        f"{m}: {len(out)} rows  cols={list(out.columns)[:6]}"
                        + (" ..." if out.shape[1] > 6 else ""),
                    )
            except Exception as e:
                report(tid, False, f"{m}: {e}")
                break

    # (The density-grid check lived here. The density map was not an MRD output
    # and the whole chain was removed in the MRD-conformance pass.)

    print("\ncolumns read downstream vs columns produced:")
    for tid, out in outputs.items():
        for c in consumers(tid):
            ct = TASKS[c]
            if ct["task"].startswith("ecoscope_workflows_ext_custom"):
                continue
            missing = column_refs(ct) - set(out.columns)
            # colormap tasks ADD their output column; layers then read it
            if missing:
                report(
                    f"{tid}->{c}",
                    False,
                    f"{ct['task']} reads missing {sorted(missing)}",
                )
            # follow one hop through apply_color_map to the layer
            if ct["task"] == "apply_color_map":
                added = set(out.columns) | {ct["partial"].get("output_column_name")}
                for c2 in consumers(c):
                    miss2 = column_refs(TASKS[c2]) - added
                    if miss2:
                        report(f"{c}->{c2}", False, f"reads missing {sorted(miss2)}")
    print(f"\n{'ALL CLEAR' if not fails else f'{fails} FAILURE(S)'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

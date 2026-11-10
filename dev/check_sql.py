"""Run the spec's own SQL against the fixture, in sqlite, exactly as
apply_sql_query would. Proves the conflict label and the species
harmonisation before a single compile."""

import json
import pathlib
import re
import sqlite3
import sys

import pandas as pd
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]

spec = yaml.safe_load((ROOT / "spec.yaml").read_text())


def find(tid):
    for s in spec["workflow"]:
        for t in s["tasks"] if s.get("type") == "task-group" else [s]:
            if t.get("id") == tid:
                return t
    raise KeyError(tid)


df = pd.read_parquet(ROOT / "mock-io" / "events.example-return.parquet")
df = df.drop(columns=["geometry"]).assign(geometry=None)
df["time"] = df["time"].astype(str)

con = sqlite3.connect(":memory:")
df.to_sql("df", con, index=False)

prep = find("events_prepared")["partial"]["query"]
con.execute("CREATE TABLE prepared AS " + prep)
p = pd.read_sql("SELECT * FROM prepared", con)
con.execute("DROP TABLE df")
p.to_sql("df", con, index=False)

print(
    f"rows {len(p)}  conflict {int(p.is_conflict.sum())}  non-conflict {int((p.is_conflict==0).sum())}"
)
print(
    "\nnon-conflict rows (must be exactly the planted Accident + Livestock + Natural):"
)
print(p[p.is_conflict == 0][["event_type", "conflict_type"]].to_string(index=False))

print("\nspecies_h over conflict rows -- one Elephant row or the harmonisation failed:")
print(
    p[p.is_conflict == 1]
    .groupby("species_h")
    .size()
    .sort_values(ascending=False)
    .to_string()
)

for tid in (
    "hwc_kpis",
    "ctype_counts",
    "species_x",
    "cas_by_species",
    "wl_by_species",
    "pred_by_species",
    "resp_counts",
    "ret_kpis",
):
    q = find(tid)["partial"]["query"]
    try:
        out = pd.read_sql(q, con)
        print(f"\n--- {tid}  ({len(out)} rows)")
        print(out.head(8).to_string(index=False))
    except Exception as e:
        print(f"\n!!! {tid} FAILED: {e}")

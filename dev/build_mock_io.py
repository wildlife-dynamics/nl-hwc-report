"""Build SYNTHETIC mock-io fixtures for the Naibunga Lower HWC report.

Every row is generated: seeded RNG, uuid5 ids, jittered points inside a
Naibunga Lower (Laikipia) bounding box. Nothing is copied from a real
EarthRanger instance -- real Naibunga event data is sensitive and stays in
gitignored `.scratch/`.

The *model* is not invented. Event-type slugs, the conditional cause fields
and the detail titles were read off naibungalower.pamdas.org during the
legacy migration (5-8 Nov 2026), after the 30 legacy types were deactivated.
Proportions follow the real instance: predation dominates, poisoning is
absent, most human-injury forms are thin.

`event_details` is stored as a JSON STRING, the same as the management
report's fixtures, because that is what apply_sql_query's sanitize step
produces from live dict values -- a parquet round-trip would otherwise turn
nested structures into numpy arrays that sanitize does not JSON-encode.

Outputs, all consumed through `mock_io_overrides` in test-cases.yaml:

  events.example-return.parquet
      Mock for get_events AND process_events_details. Both are io-tagged and
      the downstream one clobbers the upstream, so one fixture serves both.
  events-no-poisoning.example-return.parquet
      October only, and no poisoning rows -- the instance as it actually is.
  events-empty.example-return.parquet
      Zero rows, same schema.

WHAT EACH PLANTED ROW IS FOR -- delete one and a test stops proving anything:

  * One elephant spelled three ways across three event types
    ("Elephant", "elephant", "Elephant ") -- species_h must collapse them to
    ONE bar. This is the whole point of the harmonisation CASE.
  * "Baboon, Olive" on crop damage against "Olive Baboon" on predation --
    the real divergence between Naibunga's 9-value crop list and its
    70-value list.
  * A human_injury whose Cause of injury is "Accident", and a crop_damage
    whose Cause of damage is "Livestock" -- NOT conflict. They must be
    excluded from every count. If the headline total ignores the cause
    field, these two are what catches it.
  * A predation record with 0 dead and 3 injured -- "livestock killed" must
    not count injured animals.
  * Two events with no geometry -- the maps must skip them, not fail.
  * One retaliation carried out with evidence "Witnessed", one threatened
    but not carried out -- the two retaliation cards must differ.
  * One animal_carcass with Type of Death "Natural" -- a carcass that is NOT
    conflict and must not reach the wildlife-killed count.
  * One human_death whose free-text Species responsible reads "elephant"
    lowercase -- the field is free text on the live form.

Run from the inner workflow env (needs geopandas + pyarrow):
    cd ecoscope-workflows-nl-hwc-report-workflow
    pixi run python ../dev/build_mock_io.py
"""

import json
import uuid
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

OUT_DIR = Path(__file__).resolve().parents[1] / "mock-io"
RNG = np.random.default_rng(20261108)
NS = uuid.UUID("6e1b0a39-5c1d-4f7a-9a51-000000000002")

# Naibunga Lower (Laikipia, Kenya) -- rough bounding box
LON0, LON1, LAT0, LAT1 = 36.95, 37.25, 0.40, 0.65
MONTHS = [pd.Timestamp("2026-10-01T00:00:00Z"), pd.Timestamp("2026-11-01T00:00:00Z")]

FM, AH = "field_monitoring", "animal_health"

rows: list[dict] = []
_k = 0


def fid(name: str) -> str:
    return str(uuid.uuid5(NS, name))


def rand_point() -> Point:
    return Point(
        round(float(RNG.uniform(LON0, LON1)), 6),
        round(float(RNG.uniform(LAT0, LAT1)), 6),
    )


def t(month_idx: int, day: int, hour: int = 9) -> pd.Timestamp:
    # Units named explicitly and operands coerced to plain python ints. The
    # terser `pd.Timedelta(days=..., hours=...)` raised, on numpy 2:
    #   DeprecationWarning: The 'generic' unit for NumPy timedelta is
    #   deprecated, and will raise an error in the future. This includes
    #   implicit conversion of bare integers.
    # Callers pass numpy integers here (`6 + k % 8` where k comes from a
    # numpy range), which is what makes the unit generic. A warning today,
    # a build failure on some later numpy -- and this runs on every fixture
    # rebuild, so it would fail at the worst moment.
    return (
        MONTHS[month_idx]
        + pd.Timedelta(int(day) - 1, unit="D")
        + pd.Timedelta(int(hour) - 3, unit="h")
    )


def add(
    slug: str,
    display: str,
    category: str,
    details: dict,
    when: pd.Timestamp,
    geometry="random",
) -> None:
    global _k
    _k += 1
    rows.append(
        {
            "id": fid(f"event/{_k}"),
            "time": when,
            "event_type": slug,
            "event_category": category,
            "title": display,
            "priority": 0,
            "state": "resolved",
            "serial_number": str(40000 + _k),
            "event_type_display": display,
            "event_details": json.dumps(details),
            "geometry": rand_point() if geometry == "random" else geometry,
        }
    )


# --------------------------------------------------------------------------
# HWC Livestock Predation -- every record is a conflict record by definition
# --------------------------------------------------------------------------
PREDATORS = ["Spotted Hyena", "Leopard", "Lion", "Olive Baboon", "Striped Hyena"]
LIVESTOCK = ["Goat", "Sheep", "Cattle", "Donkey"]
WHERE = ["Inside boma", "Outside boma", "N/A"]

for m in (0, 1):
    for k in range(9):
        dead = int(RNG.integers(1, 9))
        injured = int(RNG.integers(0, 3))
        if m == 0 and k == 0:  # planted: injured only, nothing killed
            dead, injured = 0, 3
        taken = k % 5 == 0
        add(
            "hwc_livestock_predation",
            "HWC Livestock Predation",
            FM,
            {
                "Species": PREDATORS[k % len(PREDATORS)],
                "Livestock species": LIVESTOCK[k % len(LIVESTOCK)],
                "Total livestock dead": dead,
                "Total livestock injured": injured,
                "Animals found": WHERE[k % 3],
                "Boma construction": "Thorn" if k % 2 else "Wire",
                "Boma height (m)": round(float(RNG.uniform(1.2, 2.4)), 1),
                "Supervised?": "Night guard" if k % 3 else "No supervision",
                # PLANTED (k == 2): the live instance's predation records all carry
                # `Other (specify in notes)`, which matches none of the five named
                # response categories. Before the residual column existed, that row
                # read 0 across all five with `Any action recorded = 1` beside it.
                # This row keeps `Other / unspecified` non-zero in the base case, so
                # the residual cannot silently regress to always-zero.
                "Action": (
                    ["Other (specify in notes)"]
                    if k == 2
                    else ["Animal deterred", "Reported to KWS"]
                    if k % 2
                    else ["Reported to KWS"]
                ),
                "Retaliation action taken?": taken,
                "Retaliation action threatened?": (k % 4 == 1),
                "Evidence of retaliation": "Witnessed" if taken else None,
                "village_area": "Loshaiki",
            },
            when=t(m, 2 + k * 3, 6 + k % 8),
        )

# --------------------------------------------------------------------------
# Human injury and death. Cause decides whether it is conflict at all.
# --------------------------------------------------------------------------
# Three spellings of the same animal, on purpose -- see the module docstring.
add(
    "human_injury",
    "Human Injury",
    FM,
    {
        "Cause of injury": "Human-wildlife conflict",
        "Species responsible": "Elephant",
        "Age": "Adult",
        "Sex": "Male",
        "Action": ["Casualty transported for treatment"],
        "Incident date & time": t(0, 7, 17).isoformat(),
        "Name": "SHOULD NEVER APPEAR",
        "Telephone number": "0700000000",
    },
    when=t(0, 8, 9),
)
add(
    "human_injury",
    "Human Injury",
    FM,
    {
        "Cause of injury": "Human-wildlife conflict",
        "Species responsible": "elephant",
        "Age": "Minor",
        "Sex": "Female",
        "Action": ["Reported to KWS"],
        "Incident date & time": t(1, 4, 7).isoformat(),
    },
    when=t(1, 4, 11),
)
add(
    "human_injury",
    "Human Injury",
    FM,
    {
        "Cause of injury": "Human-wildlife conflict",
        "Species responsible": "Buffalo",
        "Age": "Adult",
        "Sex": "Male",
        "Action": [],
        "Incident date & time": t(1, 12, 6).isoformat(),
    },
    when=t(1, 12, 10),
)
# planted: NOT conflict -- must be excluded everywhere
add(
    "human_injury",
    "Human Injury",
    FM,
    {
        "Cause of injury": "Accident",
        "Species responsible": None,
        "Age": "Adult",
        "Sex": "Male",
        "Incident date & time": t(0, 15, 14).isoformat(),
    },
    when=t(0, 15, 15),
)

add(
    "human_death",
    "Human Death",
    FM,
    {
        "Cause": "Human-wildlife conflict",
        "Species responsible": "Elephant ",
        "Age": "Senior",
        "Sex": "Male",
        "Action": ["Reported to KWS"],
        "Retaliation action threatened?": True,
    },
    when=t(0, 19, 7),
)
add(
    "human_death",
    "Human Death",
    FM,
    {
        "Cause": "Human-wildlife conflict",
        "Species responsible": "buffalo",
        "Age": "Adult",
        "Sex": "Female",
        "Action": ["Reported to KWS", "Compensation claim initiated"],
    },
    when=t(1, 21, 6),
)

# --------------------------------------------------------------------------
# Crop and infrastructure damage. Conflict only when the cause is Wildlife.
# --------------------------------------------------------------------------
CROPS = ["Maize", "Beans", "Cabbage", "Tomato"]
EXTENT = ["<1 acre", "1-5 acres", "5-10 acres", ">10 acres"]
for m in (0, 1):
    for k in range(3):
        add(
            "crop_damage",
            "Crop damage",
            FM,
            {
                "Cause of damage": "Wildlife",
                # the real divergence: crop damage spells it the other way round
                "Species": "Baboon, Olive" if k == 1 else "Elephant",
                "Number of animals responsible": int(RNG.integers(1, 6)),
                "Type of crop": CROPS[k % len(CROPS)],
                "Extent of damage": EXTENT[k % len(EXTENT)],
                # The MRD's damage-type breakdown. Empty on every live record as
                # of 9 Nov 2026; present here so the column is exercised.
                "Cause of Damage - Wildlife": [
                    "Uprooting",
                    "Feeding-raiding",
                    "Trampling",
                ][k % 3],
                "Action": ["Animal deterred"]
                if k % 2
                else ["Compensation claim initiated"],
                "Incident date & time": t(m, 5 + k * 6, 5).isoformat(),
            },
            when=t(m, 5 + k * 6, 8),
        )
# planted: the only tree-crop record. No live record carries these fields, so
# without this the tree-crop table would render "No records" in every case and
# the query would never be exercised at all.
add(
    "crop_damage",
    "Crop damage",
    FM,
    {
        "Cause of damage": "Wildlife",
        "Species": "Elephant",
        "Number of animals responsible": 3,
        "Type of tree crop": ["Mango", "Banana"],
        "Extent of damage (no trees)": 12,
        "Action": ["Animal deterred"],
        "Incident date & time": t(1, 9, 5).isoformat(),
    },
    when=t(1, 9, 8),
)

# planted: livestock, not wildlife -- excluded
add(
    "crop_damage",
    "Crop damage",
    FM,
    {
        "Cause of damage": "Livestock",
        "Type of crop": "Maize",
        "Extent of damage": "1-5 acres",
        "Incident date & time": t(0, 23, 6).isoformat(),
    },
    when=t(0, 23, 9),
)

PROPERTY = ["Water_tank", "Fence", "Building"]
for m in (0, 1):
    for k in range(2):
        add(
            "infrastructure_damage",
            "Infrastructure damage",
            FM,
            {
                "Cause of damage": "Wildlife",
                "Species": "Elephant" if k == 0 else "Buffalo",
                "Number of animals responsible": int(RNG.integers(1, 4)),
                # 4 of 6 live records name more than one property, so one
                # multi-valued row keeps the combination behaviour under test.
                "Type of Property": (
                    ["Water_pipes", "Water_tank"]
                    if k == 1
                    else [PROPERTY[k % len(PROPERTY)]]
                ),
                "Extent of damage": ["Low", "Medium", "High"][k % 3],
                "Action": ["Reported to KWS"],
                "Incident date & time": t(m, 11 + k * 7, 4).isoformat(),
            },
            when=t(m, 11 + k * 7, 8),
        )

# --------------------------------------------------------------------------
# Animal health. Conflict only when the type says so.
# --------------------------------------------------------------------------
CAUSES = ["Spear", "Gunshot", "Snare", "Poisoning", "Arrow"]
for m in (0, 1):
    for k in range(3):
        add(
            "animal_carcass",
            "Animal Carcass",
            AH,
            {
                "Type of Death": "Conflict",
                "Cause of Death": CAUSES[k % len(CAUSES)],
                "Species": "Elephant" if k == 0 else ["Lion", "Spotted Hyena"][k % 2],
                "Sex": "Male" if k % 2 else "Female",
                "Animal Age": "Adult",
            },
            when=t(m, 9 + k * 5, 7),
        )
# planted: natural death -- not conflict
add(
    "animal_carcass",
    "Animal Carcass",
    AH,
    {
        "Type of Death": "Natural",
        "Cause of Death": "Drought",
        "Species": "Burchells Zebra",
        "Sex": "Female",
        "Animal Age": "Adult",
    },
    when=t(1, 17, 7),
)

for m in (0, 1):
    add(
        "sick_injured_animal",
        "Sick / Injured Animal",
        AH,
        {
            "Type of Injury": "Conflict",
            "Cause of Injury": "Snare" if m == 0 else "Spear",
            "Species": "Reticulated Giraffe" if m == 0 else "Elephant",
            "Sex": "Unknown",
            "Animal Age": "Sub-adult",
            "Action Taken": ["Retaliation evidence documented"],
        },
        when=t(m, 25, 9),
    )

# --------------------------------------------------------------------------
# Poisoning. Present in the BASE fixture only, so the empty-slot regression in
# `no_poisoning` has something to contrast with. The live instance has none.
# --------------------------------------------------------------------------
add(
    "poisoning",
    "Poisoning",
    FM,
    {
        "Suspected motive": "HWC retaliation",
        "Suspected trigger": "Livestock predation",
        "Species affected": "Vulture, White-backed",
        "Total count": 4,
        "Arrest made?": "No",
        "Date & time": t(1, 27, 6).isoformat(),
    },
    when=t(1, 27, 10),
)

# planted: two events with no location
rows[2]["geometry"] = None
rows[-4]["geometry"] = None

events = gpd.GeoDataFrame(pd.DataFrame(rows), geometry="geometry", crs=4326)
events["time"] = pd.to_datetime(events["time"], utc=True)
events = events.sort_values("time", ignore_index=True)

no_pois = events[
    (events["event_type"] != "poisoning")
    & (events["time"] < pd.Timestamp("2026-11-01T00:00:00Z"))
].reset_index(drop=True)

for name, df in {"events": events, "events-no-poisoning": no_pois}.items():
    df.to_parquet(OUT_DIR / f"{name}.example-return.parquet", index=False)
events.iloc[0:0].to_parquet(
    OUT_DIR / "events-empty.example-return.parquet", index=False
)

print(f"events: {len(events)}  no-poisoning: {len(no_pois)}  empty: 0")
print(events.groupby(["event_category", "event_type"]).size().to_string())
print(f"wrote fixtures to {OUT_DIR}")

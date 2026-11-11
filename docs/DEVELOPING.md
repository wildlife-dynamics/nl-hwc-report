# Developing this workflow

Everything here is for someone changing the spec or the report template. If you
only want to *run* the report, the [README](../README.md) is the whole story.

## Build and test

```bash
python3 dev/lint_spec.py && python3 dev/check_sql_strict.py   # seconds, no env
pixi run compile-install                                      # compile + inner lock
pixi run test --all                                           # mock-io cases
```

### The full pick-up-every-change sequence

Four artefacts are built from source and three are easy to leave stale. In this
order, every time:

```bash
# 1. offline checks -- spec shape and every SQL query through the real validator
python3 dev/lint_spec.py && python3 dev/check_sql_strict.py

# 2. rebuild fixtures and template FROM THE INNER ENV (they need pandas/docx)
cd ecoscope-workflows-nl-hwc-report-workflow
pixi run python ../dev/build_mock_io.py
pixi run python ../dev/build_report_template.py
cd ..

# 3. regenerate the workflow package from the spec
pixi run compile-install        # or `recompile` if you are about to open a PR

# 4. mock-io cases against the rebuilt fixtures
pixi run test --all

# 5. the ONE check that needs network -- is Drive serving what step 2 built?
python3 dev/check_template_sync.py
```

Step 5 is the one that has actually bitten. See *The report template* below.

### Which compile task

| task | when |
|---|---|
| `compile-install` | **anything you intend to run** — Desktop, `pixi run test` |
| `recompile` | before a PR; mirrors `_recompile.yml` (`--clobber --update`) |
| `compile` | syntax check only, with no run afterwards |

`compile` drops the inner `pixi.lock`, and that lock is required rather than
convenient: Desktop resolves and installs the inner environment from it when it
imports the template, so without it the workflow **will not load for a local
test**; `dev/run-test-cases.sh` defaults to `pixi run --locked`; and CI's
"Validate excluded files exist" step fails the build when `<WF>/pixi.lock` is
missing. It is excluded from the *diff* check — it may churn — but it must
exist.

### Three compiler workarounds

`pixi.toml` and `dev/shims/` work around three wt-compiler 0.8.3 packaging
bugs: `ruff` not importable as a module, graphviz's plugin registry never built
because pixi skips post-link scripts, and `VERSION.yaml` written to a binary
stream with ruamel's C emitter. Each is documented in full at its site. Delete
all three together when the compiler is fixed.

## The checks

| script | needs | catches |
|---|---|---|
| `dev/lint_spec.py` | nothing | non-identifier partial keys, duplicate task ids, duplicate widget titles per type, unresolved `${{ workflow.X.return }}`, layout/widget count drift |
| `dev/check_sql.py` | nothing | runs the spec's queries against the fixture in sqlite |
| `dev/check_sql_strict.py` | nothing | runs every query through the task's **real validator and authorizer** |
| `dev/check_template_sync.py` | network | whether Drive serves the template this repo builds |

`lint_spec.py`'s widget-title check exists because `merge_widget_views` and
`gather_dashboard` key a widget on `merge_key = (widget_type, title)`. Two
widgets sharing both are silently merged into one, which shifts every later
layout slot by one and renders half the dashboard in the wrong box. Nothing
upstream catches it.

`check_sql_strict.py` is what caught `json_each` being rejected — see the
limitations below.

## Test cases

| case | proves |
|---|---|
| `base` | two months, all 10 MRD sections, the conflict label across all eight types, species harmonisation, the incident-collection rule, the Word report |
| `no_poisoning` | the instance as it actually is — the Poisoning card must read 0, not vanish |
| `empty` | zero rows: skip chains hold, the report still renders, nothing raises |

What `empty` actually produces is worth knowing before you read its
`result.json` and think something broke. Zero rows means **no groups**, so the
grouped widgets produce no views at all — they are absent, not present as
placeholders. The view is `{}` and carries only the ungrouped widgets, with
`data: null`. `files` holds the .docx alone: no CSV, because
`persist_grouped_dfs_for_results_download` skips empty frames by design.

So the case proves the chains do not raise on an empty period and the report
still renders; it does not prove each widget's own placeholder. Only a period
that has *some* data can do that, which is what `Tree Crop Damage` does in
`base` — `data: null` in 2026-10, populated in 2026-11.

All cases are mock-io against **synthetic** fixtures from
`dev/build_mock_io.py`. Real Naibunga data is sensitive and stays
in gitignored `.scratch/`. Each planted row in that script exists to catch a
specific failure — the docstring says which.

## The one idea in the spec

There is no "conflict" event type. Conflict is a label derived from the event
plus its cause field, and it is derived **once**, in `events_prepared`, as
three columns every section reads:

| column | what it is |
|---|---|
| `is_conflict` | 1 when this record is a conflict incident |
| `conflict_type` | the label shown on every chart and legend |
| `species_h` | the harmonised species responsible |

| event type | counts as conflict when |
|---|---|
| `hwc_livestock_predation` | always — the event type *is* the cause |
| `human_injury` | Cause of injury = Human-wildlife conflict |
| `human_death` | Cause = Human-wildlife conflict |
| `crop_damage` | Cause of damage = Wildlife |
| `infrastructure_damage` | Cause of damage = Wildlife |
| `animal_carcass` | Type of Death = Conflict |
| `sick_injured_animal` | Type of Injury = Conflict |
| `poisoning` | Suspected motive = HWC retaliation |

Deriving it once is what makes the headline total, the species chart and the
hotspot map count the same records the same way.

**Species are harmonised before counting.** Human Injury, Predation and
Infrastructure use a 70-value list; Crop damage has its own 9-value list
spelled the other way round (`Baboon, Olive` against `Olive Baboon`); Human
Death's *Species responsible* is free text. Unharmonised, one elephant becomes
three bars.

`species_h` is deliberately **null on Animal Carcass and Sick / Injured
Animal** — their `Species` field is the animal that died, not the one
responsible. Those two sections read the raw field themselves.

## Data model

Verified against `naibungalower.pamdas.org` on 8 Nov 2026, after the legacy
migration and the deactivation of the 30 legacy event types.

| type | records | note |
|---|---:|---|
| `hwc_livestock_predation` | 116 | |
| `animal_carcass` | 131 | 88 elephants |
| `human_injury` | 35 | 28 forms empty at source |
| `infrastructure_damage` | 9 | 3 carry a species |
| `human_death` | 8 | |
| `crop_damage` | 7 | 1 carries crop type and extent |
| `sick_injured_animal` | 5 | |
| `poisoning` | **0** | the section must render as a placeholder |

Three facts that shape the spec:

- **Village is free text** on four of the five conflict events, so hotspots are
  mapped on geometry. Grouping by Patrol Block would need a Patrol Blocks
  spatial feature group in ER, which does not exist.
- **Four types have no incident-date field**, so those series fall back to ER
  event time via the same `COALESCE` rule the management report uses.
- `process_events_details` maps detail keys to display **titles**, so every
  `json_extract` here reads a title and every comparison is a display value
  (`'Wildlife'`, not `'wildlife'`). A renamed choice falls through silently —
  it shows up as an extra bar, not an error. Every title in this spec was read
  off the live v2 schemas on 9 Nov 2026; several are not what you would guess
  (`Animals found inside or outside boma`, `Species Responsible` with a capital
  R on Human Injury but lower-case on Human Death, `Evidence of retaliation?`
  with the question mark, `Cause of Death (CONFLICT)` with the bracketed
  type). Where two spellings are plausible the spec `COALESCE`s both.

### Two known limitations

**Multi-selects group as combinations.** `Type of Property` and `Type of crop`
are multi-select, and 4 of the 6 live infrastructure records name more than one
thing, so `"Water Pipes, Water Tank"` is its own row and per-property totals
cannot be read by adding rows. `json_each` would fix it — and
`apply_sql_query`'s own source lists it as readable — but opening the virtual
table trips `SQLITE_UPDATE` on `sqlite_master`, which its deny-by-default
authorizer rejects: `vtable constructor failed: json_each`. A recursive CTE is
the other route, and the validator refuses anything not starting with `SELECT`.
Section 9 of the report states the limitation rather than leaving a reader to
assume otherwise.

**Two MRD fields exist on the form and are empty on every record**:
`Type of tree crop` / `Extent of damage (no trees)` (0 of 8 crop records) and
`Cause of Damage - Wildlife`, the uprooting/trampling/feeding breakdown. Both
are wired up, so they populate the day someone starts filling them in, and
until then they read "No records for this period."

## The report template

The run form's `template_path` is pinned to a **Google Drive URL**:

```
https://drive.google.com/uc?export=download&id=1lfvoVqrk7LGdTF8mDZc2KPsQryyfpdk5
```

Sharing is `anyoneWithLink: reader`, and Drive holds it as a `.docx` blob
rather than a converted Google Doc, so the docxtpl `{%tc %}` / `{%tr %}` table
tags survive. If it stops working, check those in order: the share setting,
then that it is still a `.docx` and not a converted Doc, then the id.

Two standing costs of fetching from Drive rather than a SHA-pinned raw URL:

1. anyone with the link can read the template;
2. a published report is not reproducible — the Drive copy can be edited after
   the report was issued and nothing records that.

`resources/templates/naibunga_lower_hwc_template.docx` is the editable source
and what the test cases point at. It is a **build artefact of
`dev/build_report_template.py`** — edit that script and re-run, never the .docx
by hand, or the next build throws your edits away.

**Rebuild and re-upload together.** That is not advice, it is a bug that
happened. On 9 Nov the script gained a tree-crop table, the
retaliation-evidence tables, §12 Incident timeline and §13 Data completeness;
the repo .docx was rebuilt to 22 tables; the Drive copy stayed at 18. A run
produced a report that ended at §11 while the dashboard showed all 36 widgets,
and **nothing errored** — `create_docx` renders the tags a template happens to
contain and silently drops context for tags that are absent.
`dev/check_template_sync.py` is the only thing here that can see that gap. It
compares `word/document.xml` rather than raw bytes, because Drive's upload path
repacks the zip without changing the document.

## Downloadable results

The Files tab is a **manifest, not a directory listing**. It is populated from
`gather_dashboard`'s `files` argument; with that unset, outputs land on disk
and the app correctly says *"No downloadable results were generated"* while
Open Results Folder still shows them. The chain that fills it:

```
persist_grouped_dfs_for_results_download   writes hwc_incidents_*.csv, returns paths
  → create_files_single_view               paths → a view
  → merge_file_views                       views → GroupedFiles
  → gather_dashboard(files=…)
```

`persist_grouped_dfs_for_results_download` rather than `persist_df_wrapper`
because it embeds a 6-char hash of the group key in each filename, which is how
the front end matches a file to a dashboard view. Final layout is
`[<prefix>_]<key_hash>_<df_hash>.<ext>`.

The results **folder** holds far more than the Files tab lists: one
`persist_text` HTML per widget per view, plus a PNG for each one `create_docx`
screenshots into the report. That is by design — only the CSVs and the .docx
are registered as downloadable.

## Privacy

The casualty table and the exported CSV are column **whitelists**: name, ID
number, telephone, date of birth, ethnicity and tribe are never selected, so a
field added to the form later cannot leak into a widget, the report, or a file
someone downloads and forwards. Keep it that way — do not switch either query
to `SELECT *`.


## One view, no grouper

`set_groupers` is given `groupers: null`, which returns the **AllGrouper**;
`split_groups` then yields a single group holding the whole frame. Every chain
is written the normal grouped way — `mapvalues` over `events_grouped`, a
`_single_view` widget, `merge_widget_views` — and simply runs once.

That is deliberate and it is what makes the report whole-period. The MRD's
section list is whole-period throughout; the only month-wise outputs it names
are the by-month headline table, the seasonality series and the
damage-over-time line, and each of those derives the month in SQL from
`incident_time` rather than from the dashboard's grouping.

With a month grouper, every grouped widget rendered once per month and the Word
report repeated each figure per month — ten pie charts for one pie widget over
a ten-month period, which is what the first review flagged. To restore month
views, put the temporal grouper back in that one task; nothing else changes,
but the report will fan out again, and `create_docx`'s `ImageContextItem` has
no merge option to stop it.

## The incident rule

The MRD defines an incident as a collection:

    Total incidents = (incident collections containing >=1 qualifying conflict
    event) + (qualifying conflict events not in any collection)

`events_prepared`'s outermost SELECT adds `incident_id`, `incident_time`,
`incident_geometry` and `conflict_seq` by window function. It does **not**
collapse rows: every event survives carrying its incident, and each output
reads the level the MRD names — `conflict_seq = 1` for the headline count and
the incident map, event level for the conflict-type bar, the per-event-type
map and every loss total.

`incident_id` is `json_extract(is_contained_in, '$[0].id')` falling back to the
event's own id, and container events (`is_collection` true) are excluded in the
innermost FROM so they cannot double-count.

**This is unexercised against live data.** All 4,115 events on
`naibungalower.pamdas.org` on 10 Nov 2026 had `is_collection` false and
`is_contained_in` empty — the site is not yet grouping events into incidents.
With those columns empty the rule degrades exactly to one-event-one-incident,
so today's numbers are unchanged. The only place it is proven is `mock-io/`,
which plants one collection of three events; keep that fixture.

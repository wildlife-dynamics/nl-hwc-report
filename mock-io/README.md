# Mock-IO data

Synthetic example returns for the IO tasks, used by the `mock_io` test cases in
[`../test-cases.yaml`](../test-cases.yaml). `dev/run-test-cases.sh` points the
`WT_TASK_MOCK_IO__…` environment variables at these files.

They have the same columns and types as real Naibunga Lower EarthRanger events,
and the choice fields use the same option values and display titles, but every
name, ID, note, date, number and location is made up. Locations are random
points inside the Naibunga Lower bounding box.

**No real EarthRanger data is in this directory, or anywhere else in this
repository.** The live sample these were modelled on stays in gitignored
`.scratch/`.

| File | Case | Mocks |
|---|---|---|
| `events.example-return.parquet` | `base` | `ecoscope.platform.tasks.io.get_events`, `…io.process_events_details` |
| `events-no-poisoning.example-return.parquet` | `no_poisoning` | both of the above |
| `events-empty.example-return.parquet` | `empty` | both of the above |
| `incident-events.example-return.parquet` | *(none — see below)* | `ecoscope_workflows_ext_wd.tasks.get_incident_events` |
| `incident-events-empty.example-return.parquet` | `base`, `no_poisoning`, `empty` | the same |

One events file serves both event tasks in each case: they are both io-tagged
and both return the same event frame, so the case overrides both to the same
path.

The two `incident-events` files are **not optional**. `get_incident_events`
feeds section 4's storyboard and is the workflow's second io task, and
ecoscope-workflows-ext-wd ships no packaged example return for it — so with no
override every case fails before the DAG starts:

```
FileNotFoundError: Expected exactly 1 example-return file matching
'get-incident-events.example-return.*' in ecoscope_workflows_ext_wd.tasks
```

Their schema is taken from the task's own source, not inferred: the nine
renamed incident columns, its `keep` list of member-event columns, and the
`icon` derived from `image_url`. The empty one reproduces the frame the task
itself returns when a period contains no collections —
`GeoDataFrame(columns=["id", "incident", "geometry"])` — which is Naibunga's
state today, so section 4 renders as a placeholder in production.

The populated one is the **same Loshaiki raid** as the events fixture, seen as
`get_incident_events` returns it: one row per (incident, member event),
container excluded. The two fixtures therefore tell one story — the incident
rule collapses those three events to one in Table 1, and the storyboard draws
the same three in order.

**The populated fixture is currently wired to no case, on purpose.** Giving
`format_incident_storyboards` a non-empty frame fails on Windows with
`ValueError('Invalid format string')`, because ext-wd formats its tile dates
with `%-d` — a glibc extension the Windows C runtime rejects. The task returns
early on an empty frame, so the empty fixture never reaches it. Upstream bug,
written up in `.scratch/UPSTREAM-ext-wd-windows.md`; the file is kept here so
that wiring it back is a one-line change the day it is fixed.

## Regenerating

```bash
cd ../ecoscope-workflows-nl-hwc-report-workflow
pixi run python ../dev/build_mock_io.py
```

The builder is deterministic — a fixed seed and fixed dates — so a rebuild with
no source change produces identical files. Rebuild whenever a case needs to
cover something new, and commit the result.

**Every planted row exists to catch a specific failure, and the builder's
docstring says which.** Among them: an injury-only predation record with zero
killed; three spellings of the same animal, to prove species harmonisation
collapses them to one bar; three non-conflict records that must be excluded by
the cause test; a predation record whose `Action` is `Other (specify in
notes)`, to keep the *Other / unspecified* response column non-zero; and tree
crop damage in the second month only, to prove a widget placeholder renders in
a month with no data while the widget still populates in a month that has it.

Changing a planted row without reading that docstring will quietly remove a
regression test.

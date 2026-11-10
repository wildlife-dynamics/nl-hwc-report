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

One file serves both tasks in each case: they are both io-tagged and both
return the same event frame, so the case overrides both to the same path.

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

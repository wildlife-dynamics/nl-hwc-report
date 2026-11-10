"""Catch the spec mistakes that only wt-compiler would otherwise find.

Written after the first compile failed on:

    workflow.10.group.tasks.3.partial.by Conflict Type.[key]
      Value error, `by Conflict Type` is not a valid python identifier

The cause was an unquoted comma inside a FLOW mapping:

    partial: {title: Species Responsible, by Conflict Type}

YAML ends the value at the comma and starts a new key, so a title silently
became a second parameter. It parses fine — only the compiler's pydantic
model notices. This script notices too, in a second, without an environment.

Run before every compile:
    python3 dev/lint_spec.py
"""

from __future__ import annotations

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec.yaml"

problems: list[str] = []


def tasks(doc: dict):
    """(path, task) for every task instance, groups flattened."""
    for i, step in enumerate(doc.get("workflow") or []):
        if step.get("type") == "task-group":
            for j, t in enumerate(step.get("tasks") or []):
                yield f"workflow.{i}.group.tasks.{j}", t
        else:
            yield f"workflow.{i}", step


def main() -> int:
    raw = SPEC.read_text()
    doc = yaml.safe_load(raw)

    ids: set[str] = set()
    widget_titles: dict[tuple[str, str], str] = {}
    for path, t in tasks(doc):
        tid = t.get("id")

        # 1. the one that bit us: a partial key that is not an identifier.
        for key in t.get("partial") or {}:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(key)):
                problems.append(
                    f"{path} ({tid}): partial key {key!r} is not a python "
                    f"identifier. An unquoted comma or colon in a flow "
                    f"mapping splits the value into a new key — quote the value."
                )

        # 2. the same mistake one level down, in nested option dicts.
        def nested(obj, where):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(k, str) and k.strip() != k:
                        problems.append(
                            f"{path} ({tid}): key {k!r} in {where} has stray whitespace"
                        )
                    nested(v, where)
            elif isinstance(obj, list):
                for v in obj:
                    nested(v, where)

        nested(t.get("partial"), "partial")

        # 3. a title that lost its tail to a comma reads as a truncated
        #    sentence ending in a connective. Cheap heuristic, no false
        #    positives seen on this spec.
        title = (t.get("partial") or {}).get("title")
        if isinstance(title, str) and re.search(
            r"\b(by|in|of|and|per|with|for)$", title.strip()
        ):
            problems.append(
                f"{path} ({tid}): title {title!r} ends mid-phrase — did a comma eat the rest?"
            )

        # 4. duplicate task ids: the compiler reports these one at a time.
        if tid:
            if tid in ids:
                problems.append(f"{path}: duplicate task id {tid!r}")
            ids.add(tid)

        # 5. widget titles must be unique per widget type.
        #
        # merge_widget_views and gather_dashboard key a widget on
        # `merge_key = (widget_type, title)`. Two widgets with the same type
        # AND the same title are therefore MERGED INTO ONE -- silently, with
        # no error. You lose a dashboard slot, layout.json's one-to-one
        # mapping shifts by one from that point on, and every widget after it
        # renders in the wrong box. Nothing upstream catches this.
        t_task = str(t.get("task") or "")
        if "_widget_single_view" in t_task:
            kind = t_task.replace("create_", "").replace("_widget_single_view", "")
            title = (t.get("partial") or {}).get("title")
            if isinstance(title, str):
                if title != title.strip() or "  " in title:
                    problems.append(
                        f"{path} ({tid}): title {title!r} has stray or doubled "
                        f"whitespace -- merge_key is exact, so this will not "
                        f"merge with the title you meant"
                    )
                key = (kind, title)
                if key in widget_titles:
                    problems.append(
                        f"{path} ({tid}): widget title {title!r} is already used by "
                        f"{widget_titles[key]!r} for the same widget type ({kind}). "
                        f"They will MERGE into one widget and shift every layout "
                        f"slot after it."
                    )
                widget_titles[key] = tid

        # 5b. every widget task needs an EXPLICIT skipif.
        #
        # task-instance-defaults sets [any_is_empty_df, any_dependency_skipped].
        # Inherit that on a *_widget_single_view and, on an empty period, the
        # widget itself skips and returns a SkipSentinel. That object goes into
        # gather_dashboard's widget list and the run dies at the very end with
        #     Unable to serialize unknown type: <class 'wt_task.skip.SkipSentinel'>
        # which names no task and points at dispatch.py, so it is a genuinely
        # hard failure to trace back here. A widget must run and emit null data
        # instead -- that is what a placeholder is -- so every one of them
        # carries `skipif: {conditions: *never}`.
        if "_widget_single_view" in t_task and "skipif" not in t:
            problems.append(
                f"{path} ({tid}): widget has no explicit skipif, so it inherits "
                f"the empty-df default and will return a SkipSentinel on an "
                f"empty period -- add `skipif: {{conditions: *never}}`"
            )

    # 5c. don't feed a GROUPED task's return into a plain `partial`.
    #
    # A task with `map` or `mapvalues` runs once per group and returns a list
    # of (CompositeFilter, value) tuples -- never a bare value, even when there
    # is only one group. Hand that to a task expecting a plain argument and it
    # fails at runtime with a pydantic error that quotes the whole tuple, e.g.
    #     Input is not a valid path for <class 'pathlib.Path'>
    #     input_value=((('All', '=', 'True'),), '...conflict_type_bar.html')
    # The fix is always the same: consume it with `map` (or `mapvalues`) so the
    # task sees the view and the value separately.
    #
    # The allowlist is the handful of tasks whose job IS to take grouped input.
    GROUPED_OK = {
        "merge_widget_views",
        "merge_file_views",
        "gather_dashboard",
        "persist_grouped_dfs_for_results_download",
        "ecoscope_workflows_ext_custom.tasks.results.create_docx",
    }
    grouped = {
        t.get("id")
        for _, t in tasks(doc)
        if ("map" in t or "mapvalues" in t) and t.get("id")
    }
    for path, t in tasks(doc):
        if str(t.get("task")) in GROUPED_OK:
            continue
        for key, val in (t.get("partial") or {}).items():
            for ref in re.findall(r"workflow\.([A-Za-z0-9_]+)\.return", str(val)):
                if ref in grouped:
                    problems.append(
                        f"{path} ({t.get('id')}): partial.{key} takes "
                        f"{ref!r}, which is GROUPED (it has map/mapvalues) and "
                        f"returns (view, value) tuples, not a plain value. "
                        f"Consume it with `map`/`mapvalues` instead."
                    )

    # 6. every ${{ workflow.X.return }} must name a task that exists.
    refs = set(re.findall(r"workflow\.([A-Za-z0-9_]+)\.return", raw))
    for missing in sorted(refs - ids):
        problems.append(
            f"reference to ${{{{ workflow.{missing}.return }}}} but no task has that id"
        )

    # 7. every dashboard widget needs a layout slot, and vice versa.
    layout = yaml.safe_load((ROOT / "layout.json").read_text())
    dash = next((t for _, t in tasks(doc) if t.get("id") == "dashboard"), None)
    if dash and layout is not None:
        n_widgets = len((dash.get("partial") or {}).get("widgets") or [])
        slots = sorted(s["widget_id"] for s in layout)
        if slots != list(range(n_widgets)):
            problems.append(
                f"layout.json has slots {slots[:3]}..{slots[-3:]} "
                f"({len(slots)}) but gather_dashboard lists {n_widgets} widgets — "
                f"they must be 0..{n_widgets - 1} with no gaps"
            )

    for p in problems:
        print("  " + p)
    print(f"\n{len(problems)} problem(s). {len(ids)} task instances.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

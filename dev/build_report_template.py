"""Build the Word template for the Naibunga Lower HWC report.

Writes resources/templates/naibunga_lower_hwc_template.docx, a docxtpl
(Jinja2) template rendered by ext-custom's `create_docx` task. Values are
XML-escaped with |e because create_docx renders without autoescape -- a bare
"&" or "<" in a species name or a free-text cause would otherwise be dropped
from the document without an error.

Re-run this script instead of hand-editing the .docx whenever the report
layout or the context keys in spec.yaml's `create_report` task change. The
.docx is a build artefact of this file; editing it by hand means the next run
silently throws your edits away.

Context contract -- keys must match `create_report.context.items` in spec.yaml:
  report_date   timerange -> "{{ report_date }}"
  prepared_by   text      -> "{{ prepared_by }}"
  <table keys>  table -> {key}.col_labels / {key}.tbl_contents
                grouped tables (merge_groups=True) carry a first "Group"
                column; period_* tables are ungrouped
  <image keys>  grouped image -> list of {title, image}
  storyboards                  -> a single image (NOT a list); every other
                                  figure is grouped, including the two
                                  per-month charts

Logos are embedded from resources/images/: the Naibunga Lower logo on the
cover and on the right of the footer, the Ecoscope logo on the left.

WHERE THIS FILE GOES AFTER YOU BUILD IT

spec.yaml pins `template_path` to a Google Drive URL (it is not a form
field), so the built .docx has to be uploaded there as a NEW VERSION of the
same Drive file, keeping the file id. The repo copy is the editable source.
Rebuild and re-upload together, or the published report and this file drift.

Run with any Python that has python-docx, e.g. from the inner workflow env:
    cd ecoscope-workflows-nl-hwc-report-workflow
    pixi run python ../dev/build_report_template.py
"""

from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "resources" / "templates" / "naibunga_lower_hwc_template.docx"
LOGO_NL = ROOT / "resources" / "images" / "naibunga_lower_logo.jpg"
LOGO_ECO = ROOT / "resources" / "images" / "ecoscope_logo.png"

BLACK = RGBColor(0x00, 0x00, 0x00)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREY = RGBColor(0x40, 0x40, 0x40)
HEADER_FILL = "5B9BD5"  # light blue; dark enough for white bold text to read

doc = Document()
section = doc.sections[0]
section.orientation = WD_ORIENT.PORTRAIT
section.page_width, section.page_height = Cm(21.0), Cm(29.7)
for side in ("left_margin", "right_margin"):
    setattr(section, side, Cm(1.8))
section.top_margin = section.bottom_margin = Cm(1.8)
TEXT_WIDTH = section.page_width - section.left_margin - section.right_margin

normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(10)
for level, size in ((1, 16), (2, 13), (3, 11)):
    style = doc.styles[f"Heading {level}"]
    style.font.size = Pt(size)
    style.font.color.rgb = BLACK

_table_no = 0
_fig_no = 0


def para(
    text: str,
    style: str | None = None,
    *,
    center: bool = False,
    size: int | None = None,
    italic: bool = False,
    bold: bool = False,
    color: RGBColor | None = None,
):
    p = doc.add_paragraph(text, style=style)
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in p.runs:
        if size:
            run.font.size = Pt(size)
        run.italic = italic
        run.bold = bold
        if color is not None:
            run.font.color.rgb = color
    return p


def about(text: str) -> None:
    """A short note for the reader on what a section shows and how to read it."""
    para(text, size=9, color=GREY)


def caption(
    kind: str,
    title: str,
    *,
    center: bool = False,
    below: bool = False,
    suffix: str = "",
):
    """'Table 3. Title' / 'Fig. 2. Title' -- bold label, plain title.

    THE NUMBER IS COUNTED AT RENDER TIME by the Jinja namespace `ns` (set once
    after the cover), not written in here. With the optional month grouping a
    grouped figure repeats once per month, so a number fixed at build time
    would repeat too; the counter gives Fig. 1, 2, 3 ... in reading order
    whatever the grouping. `suffix` is extra Jinja after the title -- the
    "(Jan 2026)" of a per-month figure.

    `below=True` is for figure captions, which sit UNDER their figure.

    THE ANCHORING BUG THE REVIEW FOUND -- "Could you make sure all figure
    captions are anchored directly underneath their corresponding output?"
    Every caption used to set keep_with_next, which binds a paragraph to the
    one that FOLLOWS it. On a table caption that is right: it keeps the caption
    with its table. On a figure caption it is exactly wrong -- it bound the
    caption to the next heading and let Word break the page between the figure
    and its own caption. A figure caption instead needs no keep_with_next of
    its own, and the figure above it carries keep_with_next so the pair moves
    together.
    """
    global _table_no, _fig_no
    counter = "t" if kind == "Table" else "f"
    if counter == "t":
        _table_no += 1
    else:
        _fig_no += 1
    label = "Table" if kind == "Table" else "Fig."
    p = doc.add_paragraph()
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    lab = p.add_run(
        f"{{% set ns.{counter} = ns.{counter} + 1 %}}{label} {{{{ ns.{counter} }}}}. "
    )
    lab.bold = True
    lab.font.size = Pt(9)
    t = p.add_run(title + suffix)
    t.italic = True
    t.font.size = Pt(9)
    p.paragraph_format.space_before = Pt(2 if below else 8)
    p.paragraph_format.space_after = Pt(12 if below else 4)
    p.paragraph_format.keep_with_next = not below
    return p


def month_label(var: str) -> str:
    """Jinja printing a "2026-01" group value as "Jan 2026", anything else as is.

    Same helper as the management report. The month grouper's values are
    "%Y-%m"; only the display changes.
    """
    m = "'JanFebMarAprMayJunJulAugSepOctNovDec'"
    return (
        f"{{% if {var} is string and {var}|length == 7 and {var}[4:5] == '-' %}}"
        f"{{{{ {m}[({var}[5:7]|int - 1) * 3:({var}[5:7]|int) * 3] }}}} {{{{ {var}[:4] }}}}"
        f"{{% else %}}{{{{ {var}|e }}}}{{% endif %}}"
    )


# " (Jan 2026)" after a per-month figure's title. The whole-period view's
# title is the AllGrouper's "True", which is not shown.
GROUP_SUFFIX = (
    "{% if item.title and item.title|string != 'True' %} ("
    + month_label("item.title")
    + "){% endif %}"
)


def shade(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def table(key: str, title: str) -> None:
    """A captioned, dynamic-column table bound to one table context item."""
    caption("Table", title)
    para(f"{{%p if {key}.tbl_contents %}}")
    t = doc.add_table(rows=4, cols=3)
    t.style = "Table Grid"
    header, open_row, body, close_row = t.rows
    header.cells[0].text = f"{{%tc for col in {key}.col_labels %}}"
    header.cells[1].text = "{{ col|e }}"
    header.cells[2].text = "{%tc endfor %}"
    for cell in header.cells:  # the middle cell is the one repeated
        shade(cell, HEADER_FILL)
        for p in cell.paragraphs:
            for run in p.runs:
                run.bold = True
                run.font.color.rgb = WHITE
    open_row.cells[0].text = f"{{%tr for row in {key}.tbl_contents %}}"
    body.cells[0].text = "{%tc for col in row.cols %}"
    body.cells[1].text = "{{ col|e }}"
    body.cells[2].text = "{%tc endfor %}"
    close_row.cells[0].text = "{%tr endfor %}"
    para("{%p else %}")
    para("No records for this period.", italic=True, size=9)
    para("{%p endif %}")


def images(
    key: str,
    title: str,
    *,
    empty: str = "No records for this period.",
    note: str | None = None,
    outside: str | None = None,
) -> None:
    """A GROUPED image item -- anything built from `events_grouped`.

    create_docx hands a grouped value to the template as a LIST of
    {title, groups, image} dicts, even when there is exactly one group. So it
    must be looped over: `{{ key }}` on a list renders nothing at all, silently,
    which is how 18 of 22 figures came out blank while their captions stayed.

    With the AllGrouper there is one iteration, so this produces exactly one
    figure. `item.title` is deliberately NOT in the caption: it would read
    "True" (the all-index value), not a month.

    THE CAPTION IS OUTSIDE THE LOOP. Review 0.2: "Figure numbering skips Fig.
    18 (goes from 17 to 19 in this section)." Fig. 18 (tree crops) had no data,
    create_docx dropped its skipped view, the list came through empty, and the
    loop -- caption included -- rendered nothing, so the number vanished with
    it. Now the caption always prints and an empty figure prints `empty`
    above it instead of an image, so the numbering is the same in every
    report. `key is string` covers the other way a figure can be missing: when
    the whole item is skipped, create_docx substitutes `missing_text`, a plain
    string, which must not be looped over character by character.
    """
    para(f"{{%p if {key} is string or not {key} %}}")
    ph = para(empty, center=True, italic=True, size=9, color=GREY)
    ph.paragraph_format.keep_with_next = True
    ph.paragraph_format.space_after = Pt(0)
    cap = caption("Fig", title, center=True, below=True)
    para("{%p else %}")
    para(f"{{%p for item in {key} %}}")
    img = para("{{ item.image }}", center=True)
    img.paragraph_format.keep_with_next = True
    img.paragraph_format.space_after = Pt(0)
    cap = caption("Fig", title, center=True, below=True, suffix=GROUP_SUFFIX)
    para("{%p endfor %}")
    para("{%p endif %}")
    if note:
        n = para(note, center=True, size=8, color=GREY)
        n.paragraph_format.space_before = Pt(0)
        n.paragraph_format.space_after = Pt(10)
    # Review 0.3: "add a note under the map for any points beyond it ('N
    # reports fall outside the map area')". `outside` is a one-row table item
    # holding the sentence, or no rows when every report is on the map.
    if outside:
        para(f"{{%p if {outside} is not string and {outside}.tbl_contents %}}")
        o = para(
            f"{{{{ {outside}.tbl_contents[0].cols[0]|e }}}}",
            center=True,
            italic=True,
            size=8,
            color=GREY,
        )
        o.paragraph_format.space_before = Pt(0)
        o.paragraph_format.space_after = Pt(10)
        para("{%p endif %}")


def single_image(key: str, title: str) -> None:
    """An UNGROUPED image item -- built straight from `events_indexed`.

    create_docx passes one InlineImage, not a list, so it must NOT be looped
    over ('InlineImage' object is not iterable). Only the whole-period charts
    qualify: the seasonality series, the damage-over-time series and the
    incident storyboards.
    """
    img = para(f"{{{{ {key} }}}}", center=True)
    img.paragraph_format.keep_with_next = True
    img.paragraph_format.space_after = Pt(0)
    caption("Fig", title, center=True, below=True)


# ---------------------------------------------------------------- footer
footer = section.footer.paragraphs[0]
footer.style = doc.styles["Normal"]  # the Footer style's centre tab would catch the tab
footer.paragraph_format.tab_stops.add_tab_stop(TEXT_WIDTH, WD_TAB_ALIGNMENT.RIGHT)
footer.add_run().add_picture(str(LOGO_ECO), height=Cm(0.8))
footer.add_run("\t")
footer.add_run().add_picture(str(LOGO_NL), height=Cm(1.3))

# ---------------------------------------------------------------- cover
logo = doc.add_paragraph()
logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
logo.paragraph_format.space_before = Cm(3)
logo.add_run().add_picture(str(LOGO_NL), width=Cm(6))
para(
    "Naibunga Lower Conservancy", center=True, size=26
).paragraph_format.space_before = Cm(1.5)
para("Human-Wildlife Conflict Report", center=True, size=18)
para("{{ report_date }}", center=True, size=14)
para("Prepared by: {{ prepared_by|e }}", center=True, size=11)
doc.add_page_break()
para("{%p set ns = namespace(t=0, f=0) %}")

# =========================================================================
# THE MRD'S REPORT SECTIONS, IN THE MRD'S ORDER.
#
# Sections 1-9, renumbered after the review dropped the old section 5
# (Seasonality) and moved its chart into section 2. Section numbers in this
# document therefore no longer line up with the MRD's outline from section 5
# onward: MRD 6 Human injury/death is section 5 here, and so on down to MRD 11
# Retaliation as section 9.
#
# `images()` for anything built from events_grouped, `single_image()` for the
# three charts built straight from events_indexed. Getting that wrong fails
# loudly in one direction ("'InlineImage' object is not iterable") and
# SILENTLY in the other -- `{{ key }}` on a list renders nothing at all, which
# is how 18 of 22 figures once came out blank with their captions intact.
#
# Do not add a section that the MRD does not list. The first review of this
# report failed on exactly that: extra summary tables and a figure repeated
# once per month.
# =========================================================================

# ---------------------------------------------------------------- 1. summary
doc.add_heading("1. Summary", level=1)
about(
    "Human-wildlife conflict recorded by Naibunga Lower Conservancy in "
    "EarthRanger over the reporting period."
)
about(
    "An incident is a group of related events recorded together, or a single "
    "event that stands alone. Losses are counted per event or per victim, so "
    "one incident can account for several injured people or several animals "
    "killed -- the incident total and the loss totals are not meant to match."
)
about(
    "What counts as a conflict incident: every livestock predation report; a "
    "human injury or death caused by wildlife; crop or infrastructure damage "
    "caused by wildlife; a wildlife death or injury recorded as conflict; and "
    "a poisoning carried out in retaliation."
)
# Review question: "What have you used to calculate total incidents? It looks
# like total events rather than incidents." The rule is implemented as the MRD
# defines it; the two numbers coincide at Naibunga today because no events are
# linked into collections, and a reader deserves to know that rather than
# assume the count is wrong.
about(
    "Where several reports are linked together into one incident in "
    "EarthRanger they are counted once, as a single incident. Conflict reports "
    "at Naibunga Lower are not yet being linked, so the number of incidents "
    "currently equals the number of conflict events recorded."
)
table("period_kpis", "Headline figures for the whole period")

# ---------------------------------------------------------------- 2. conflict type
doc.add_heading("2. Type of conflict", level=1)
# Review 0.2: keep the incident-map wording "for the incident map caption or
# description" and add "Each point is one conflict report." for the event map.
# Each sentence now sits under the map it describes, so the section intro only
# says what the section is.
about(
    "How conflict divides between the different kinds of conflict, when it "
    "happened, and where. A conflict type keeps the same colour in every chart "
    "and on every map in this report."
)
# Review 0.3: map extents from each map's own data.
about(
    "Each map shows the whole conservancy and every report within about 20 km "
    "of it, with a margin of about 2 km. Reports further away are counted in "
    "a note under the map. Reports with no location, or at an impossible one "
    "(0,0 or outside East Africa), are left off the maps and out of that note."
)
images("ctype_bar", "Conflict events by type")
images("conflict_trend", "Conflict events per month by type")
# Review 0.2: "only render the incident map when the period contains at least
# one incident collection. Otherwise show a placeholder ('No linked incidents in
# this period, see Fig. 4') so figure numbering stays consistent." The spec
# empties the incident map's frame when nothing is linked; the caption below
# always prints, so Fig. 4 stays Fig. 4.
images(
    "incident_map",
    "Conflict incidents",
    empty="No linked incidents in this period, see Fig. {{ ns.f + 2 }}.",
    note=(
        "Each point is one incident. Where an incident includes several linked "
        "reports, it is mapped at the location of the earliest one."
    ),
)
images(
    "event_map",
    "Conflict events",
    note="Each point is one conflict report.",
    outside="event_map_outside",
)

# ---------------------------------------------------------------- 3. species
doc.add_heading("3. Species responsible", level=1)
about(
    "Which wildlife species caused conflict, broken down by kind of conflict. "
    "'Unknown' means the species was not recorded for that incident. Wildlife "
    "that were themselves killed or injured are reported in Section 6."
)
images("species_bar", "Species responsible")

# ---------------------------------------------------------------- 4. storyboard
doc.add_heading("4. Incident storyboard", level=1)
about(
    "How the events making up each incident unfolded, in the order they were "
    "reported. This shows every incident whose reports have been linked "
    "together in EarthRanger in the period -- including any linked incident "
    "that is not human-wildlife conflict -- and is empty while none are."
)
single_image("storyboards", "Incident storyboards")

# ---------------------------------------------------------------- 5. people
doc.add_heading("5. People injured and killed", level=1)
about(
    "People injured or killed by wildlife, by the species responsible. Names, "
    "ID numbers and telephone numbers are not included in this report."
)
images("casualties_bar", "Human casualties by species responsible")
table("cas_table", "Casualty record")

# ---------------------------------------------------------------- 6. wildlife
doc.add_heading("6. Wildlife killed and injured", level=1)
about(
    "Wildlife killed or injured as a result of conflict, by species and by "
    "cause. Deaths and injuries from natural causes, disease or poaching are "
    "not included here."
)
images("wildlife_bar", "Wildlife killed and injured by species")
images("wildlife_cause_bar", "Cause of wildlife death or injury")
images(
    "wildlife_map",
    "Wildlife killed or injured in conflict",
    outside="wildlife_map_outside",
)

# ---------------------------------------------------------------- 7. predation
doc.add_heading("7. Livestock predation", level=1)
about(
    "Livestock killed or injured by predators: which livestock were lost, "
    "which predators were responsible, and whether animals were inside or "
    "outside a boma when attacked. One report records one total killed, so a "
    "report naming several kinds of livestock is shown as 'Several species'."
)
images("predation_bar", "Livestock killed and injured by livestock species")
images("predator_bar", "Predators responsible, by livestock killed")
images(
    "predation_map",
    "Predation events, point size reflects number of livestock killed",
    note=(
        "Colour shows the predator. Point size shows livestock killed, as in "
        "the key along the bottom of the map: 0 or 1, 2 to 4, 5 or more."
    ),
    outside="predation_map_outside",
)
images("boma_pie", "Where attacks happened")

# ---------------------------------------------------------------- 8. damage
doc.add_heading("8. Crop and infrastructure damage", level=1)
about(
    "Damage caused by wildlife to crops and to property such as fences, water "
    "tanks and pipes, by type and by the extent of the damage. Crop damage is "
    "measured in acres and infrastructure damage on a low-to-high scale, so "
    "the two are never charted on one axis."
)
about(
    "A report naming more than one crop is shown as 'Several crops'. A report "
    "naming more than one kind of property is shown under that combination, "
    "so property totals cannot be read by adding rows. Damage type and "
    "tree-crop figures depend on form fields that are not yet being filled "
    "in, and will read as no records until they are."
)
images("damage_trend", "Crop and infrastructure damage over time")
images("crop_bar", "Crop damage incidents by species responsible and crop")
images("damage_extent_bar", "Crop damage extent by damage type")
images("tree_bar", "Tree crop damage by tree type")
images("infra_bar", "Infrastructure damage by property type and damage extent")
images(
    "crop_map",
    "Crop damage locations",
    note=(
        "Each point is one report, coloured by the extent of damage. Reports "
        "made at the same place overlap."
    ),
    outside="crop_map_outside",
)
images(
    "infra_map",
    "Infrastructure damage locations",
    note=(
        "Each point is one report, coloured by the extent of damage. Reports "
        "made at the same place overlap."
    ),
    outside="infra_map_outside",
)

# ---------------------------------------------------------------- 9. retaliation
doc.add_heading("9. Retaliation against wildlife", level=1)
about(
    "Conflict incidents where people threatened or carried out retaliation "
    "against wildlife, in total and by the species involved. An incident can "
    "be both threatened and carried out, so the two figures overlap."
)
table("ret_kpis", "Retaliation threatened and carried out")
images("retaliation_bar", "Retaliation by species responsible")

# ---------------------------------------------------------------- notes
# Review feedback: "Where values are 'Not recorded' (e.g. sections 7 & 8) - is
# this due to legacy records not being carried over properly? I think we should
# add a footnote on this."
#
# Stated as what can be verified from the data model rather than as a
# diagnosis: the field is blank at source. It is worth being precise that this
# is not a migration defect, because the obvious reading of a column full of
# "Not recorded" is that something was lost on the way in.
doc.add_heading("About the figures in this report", level=2)
# Review 0.2: "'Not recorded' values: can you please confirm these are accurate
# and not an issue with the historic data migration? E.g. in Fig. 14, 83% are
# 'Not recorded'." Checked record by record in EarthRanger on 19 Nov 2026: of
# the 12 predation reports Jan-Nov 2026, the 10 blanks are all reports made on
# the old "hwc_livestock" form and copied onto the current one; that form had
# no boma question at all (nor action taken or retaliation), so there was
# nothing to copy. Both reports made on the current form answer it. The text
# below says that generally, because the shares change with the period.
about(
    "'Not recorded' means the field is blank on the report -- not that "
    "something was investigated and came back unknown -- and is shown in grey "
    "in every chart and map. Most blanks are reports first made on the older "
    "EarthRanger forms and copied onto the current ones in 2026. The older "
    "forms did not ask every question the current ones do -- the livestock "
    "form, for example, had no question about the boma, the action taken or "
    "retaliation -- so for those reports there was no answer to copy. The "
    "remaining blanks are optional questions left unanswered on the current "
    "forms. No record was lost: every event, with its date and location, is "
    "counted in every total."
)
about(
    "Figures are numbered in the order they appear. A figure with no data for "
    "the period is shown as an empty panel rather than removed, so the "
    "numbering is stable between one month's report and the next."
)


OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
print(f"wrote {OUT}  ({_table_no} table and {_fig_no} figure captions)")

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
                monthly tables (merge_groups=True) carry a first "Group"
                column with the month; period_* tables are ungrouped
  <image keys>  grouped image -> list of {title, image}
  conflict_trend               -> a single image (NOT a list)

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


def caption(label: str, title: str, *, center: bool = False):
    """'Table 3. Title' / 'Fig. 2. Title' -- bold label, plain title."""
    p = doc.add_paragraph()
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    lab = p.add_run(label + " ")
    lab.bold = True
    lab.font.size = Pt(9)
    t = p.add_run(title)
    t.italic = True
    t.font.size = Pt(9)
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    return p


def shade(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def table(key: str, title: str) -> None:
    """A captioned, dynamic-column table bound to one table context item."""
    global _table_no
    _table_no += 1
    caption(f"Table {_table_no}.", title)
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


def images(key: str, title: str) -> None:
    """A GROUPED image item -- anything built from `events_grouped`.

    create_docx hands a grouped value to the template as a LIST of
    {title, groups, image} dicts, even when there is exactly one group. So it
    must be looped over: `{{ key }}` on a list renders nothing at all, silently,
    which is how 18 of 22 figures came out blank while their captions stayed.

    With the AllGrouper there is one iteration, so this produces exactly one
    figure. `item.title` is deliberately NOT in the caption: it would read
    "True" (the all-index value), not a month.
    """
    global _fig_no
    _fig_no += 1
    para(f"{{%p for item in {key} %}}")
    para("{{ item.image }}", center=True)
    caption("", title, center=True)
    para("{%p endfor %}")


def single_image(key: str, title: str) -> None:
    """An UNGROUPED image item -- built straight from `events_indexed`.

    create_docx passes one InlineImage, not a list, so it must NOT be looped
    over ('InlineImage' object is not iterable). Only the three whole-period
    charts qualify: the incident timeline, the seasonality series and the
    damage-over-time line.
    """
    global _fig_no
    _fig_no += 1
    para(f"{{{{ {key} }}}}", center=True)
    caption("", title, center=True)


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

# =========================================================================
# THE MRD'S REPORT SECTIONS, IN THE MRD'S ORDER.
#
# Every figure is a single_image: there is no grouper, so each image key
# receives one path and a `for item in key` loop would fail with
# "'InlineImage' object is not iterable". Month appears only where the MRD
# puts it -- Table 2, the seasonality series and the damage-over-time line --
# and each of those derives the month in SQL, not from a dashboard grouping.
#
# Do not add a section that the MRD does not list. The first review of this
# report failed on exactly that: extra summary tables and a figure repeated
# once per month.
# =========================================================================

# ---------------------------------------------------------------- 1. summary
doc.add_heading("1. Summary", level=1)
about(
    "Human-wildlife conflict recorded by Naibunga Lower Conservancy in "
    "EarthRanger over the reporting period. Table 1 gives the totals for the "
    "whole period and Table 2 the same figures month by month."
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
table("period_kpis", "Headline figures for the whole period")
table("month_kpis", "Headline figures by month")

# ---------------------------------------------------------------- 2. conflict type
doc.add_heading("2. Type of conflict", level=1)
about(
    "How conflict divides between the different kinds of conflict, and where "
    "it happened. Each point on the map is one incident, at the incident's "
    "location -- the first child event's position where several events were "
    "recorded together."
)
images("ctype_bar", "Conflict incidents by type")
images("incident_map", "Where conflict happened")

# ---------------------------------------------------------------- 3. species
doc.add_heading("3. Species responsible", level=1)
about(
    "Which wildlife species caused conflict, broken down by kind of conflict. "
    "'Unknown' means the species was not recorded for that incident. Wildlife "
    "that were themselves killed or injured are reported in Section 7."
)
images("species_bar", "Species responsible")

# ---------------------------------------------------------------- 4. timeline
doc.add_heading("4. Incident timeline", level=1)
about(
    "Every conflict incident in time order, with the gap since the previous "
    "one. Clusters of short gaps mark periods of sustained conflict."
)
single_image("timeline_plot", "Incident timeline")

# ---------------------------------------------------------------- 5. seasonality
doc.add_heading("5. Seasonality", level=1)
about(
    "Conflict incidents per month across the whole reporting period, by "
    "conflict type, to show when conflict rises and falls through the year."
)
single_image("conflict_trend", "Conflict incidents per month by type")

# ---------------------------------------------------------------- 6. people
doc.add_heading("6. People injured and killed", level=1)
about(
    "People injured or killed by wildlife, by the species responsible. Names, "
    "ID numbers and telephone numbers are not included in this report."
)
images("casualties_bar", "Human casualties by species responsible")
table("cas_table", "Casualty record")

# ---------------------------------------------------------------- 7. wildlife
doc.add_heading("7. Wildlife killed and injured", level=1)
about(
    "Wildlife killed or injured as a result of conflict, by species and by "
    "cause. Deaths and injuries from natural causes, disease or poaching are "
    "not included here."
)
images("wildlife_bar", "Wildlife killed and injured by species")
images("wildlife_cause_bar", "Cause of wildlife death or injury")
images("wildlife_map", "Wildlife killed or injured in conflict")

# ---------------------------------------------------------------- 8. predation
doc.add_heading("8. Livestock predation", level=1)
about(
    "Livestock killed or injured by predators: which livestock were lost, "
    "which predators were responsible, and whether animals were inside or "
    "outside a boma when attacked. The map sizes each point by the number of "
    "livestock killed."
)
images("predation_bar", "Livestock killed and injured by livestock species")
images("predator_bar", "Predators responsible")
images("predation_map", "Predation events, sized by livestock killed")
images("boma_pie", "Where attacks happened")

# ---------------------------------------------------------------- 9. damage
doc.add_heading("9. Crop and infrastructure damage", level=1)
about(
    "Damage caused by wildlife to crops and to property such as fences, water "
    "tanks and pipes, by type and by the extent of the damage."
)
about(
    "Where a record names more than one crop or property, the combination is "
    "its own category -- so per-item totals cannot be read by adding rows. "
    "Damage type and tree-crop figures depend on form fields that are not yet "
    "being filled in, and will read as no records until they are."
)
images("crop_bar", "Crop damage incidents by crop")
images("damage_extent_bar", "Extent of damage by damage type")
images("tree_bar", "Tree crop damage by tree type")
images("infra_bar", "Infrastructure damage by property type")
single_image("damage_trend", "Crop and infrastructure damage over time")
images("crop_map", "Crop damage locations")
images("infra_map", "Infrastructure damage locations")

# ---------------------------------------------------------------- 10. retaliation
doc.add_heading("10. Retaliation against wildlife", level=1)
about(
    "Conflict incidents where people threatened or carried out retaliation "
    "against wildlife, in total and by the species involved."
)
table("ret_kpis", "Retaliation threatened and carried out")
images("retaliation_bar", "Retaliation by species responsible")


OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
print(f"wrote {OUT}  ({_table_no} tables, {_fig_no} figures)")

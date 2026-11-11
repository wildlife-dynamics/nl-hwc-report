# Naibunga Lower Human-Wildlife Conflict Report — User Guide

This guide walks you through running the Naibunga Lower HWC Report, which reads
human-wildlife conflict events from EarthRanger and produces an interactive
dashboard and a Word report for a period you choose.

## Overview

Each run delivers:

- **A dashboard** — 33 widgets across the 10 report sections, covering the
  whole period you choose.
- **A Word report** (`naibunga_lower_hwc_report_<hash>.docx`) — the same
  material written out with headings, numbered tables and figures, ready to
  send or print.
- **A CSV** (`hwc_incidents_<hash>_<hash>.csv`) — every conflict incident in
  the period, one row each, for your own analysis.

The report answers, for the period: how many conflict incidents occurred and of
what kind, which species were responsible, where incidents cluster, who and
what was lost, and how often retaliation against wildlife was threatened or
carried out.

Everything is reported for the **whole period at once**. Month-by-month
figures appear where they are useful — the headline table by month, the
seasonality chart and the damage-over-time chart — rather than by repeating
every chart for every month.

## Prerequisites

- Ecoscope Desktop, or another Ecoscope workflow runner.
- Access to an EarthRanger instance carrying the eight event types below, with
  a username and password you can use.

## Step 1 — Add the workflow template

In the runner, go to **Workflow Templates** and click **Add Workflow
Template**. Paste this into the **Github Link** field:

```
https://github.com/wildlife-dynamics/nl-hwc-report.git
```

Click **Add Template**. The card may show *Initializing…* for a minute or two
while the environment is built. This happens once.

## Step 2 — Add an EarthRanger connection

Go to **Data Sources** and click **Connect**. Choose **EarthRanger**, then fill
in:

| Field | Value |
|---|---|
| Data Source Name | a label you will recognise, e.g. `Naibunga Lower` |
| EarthRanger URL | your instance, e.g. `naibungalower.pamdas.org` |
| EarthRanger Username | your username |
| EarthRanger Password | your password |

Click **Connect**. Credentials are not checked at this point — a wrong password
shows up as an error when the workflow runs, not here.

## Step 3 — Select the workflow

The template appears in **Workflow Templates** as `nl-hwc-report`. Click it to
open the run form.

## Step 4 — Fill in the form

Four sections, none of them long.

**Workflow Details**

| Field | What it does |
|---|---|
| Workflow Name | names this run in the runner's list |
| Workflow Description | optional; appears on the Word report cover |

**Data Source** — pick the EarthRanger connection from Step 2.

**Time Range** — a timezone, a **Since** date and an **Until** date. Everything
in the report is drawn from events in this window, and the month-by-month
breakdown comes from splitting it.

**Base Maps** — the background for the maps. The defaults (a topographic layer
with satellite imagery over it at half opacity) are fine; change them only if
you prefer a different backdrop.

The report template itself is not in the form. It is fetched automatically when
the workflow runs.

Click **Submit**.

## What the run does

1. Fetches every event in your time range from EarthRanger.
2. Works out which of them count as conflict, and what kind (see *How incidents
   are counted*, below).
3. Builds the charts, tables and maps for the period.
4. Downloads the Word template and fills it in.
5. Writes everything to the results folder and assembles the dashboard.

A two-month run takes a few minutes. Most of that is rendering maps.

## Reading the dashboard

Ten sections, in the same order as the Word report.

| # | Section | What it tells you |
|---|---|---|
| 1 | **Summary** | Nine cards: incidents, people injured and killed, livestock injured and killed, wildlife injured and killed, poisonings, retaliation. Your top-line numbers. |
| 2 | **Type of conflict** | How incidents split between predation, crop damage, infrastructure damage, human injury, human death and wildlife death, and a map of where they happened — one point per incident. |
| 3 | **Species responsible** | Which animals caused conflict, and which kind. |
| 4 | **Incident timeline** | Each incident against the gap in days since the one before. A run of points near zero is a burst of conflict; a tall spike is a quiet spell. |
| 5 | **Seasonality** | Incidents per month, by type. Shows when conflict rises and falls through the year. |
| 6 | **People injured and killed** | Casualties by the species responsible, and a record of each one with location and action taken. |
| 7 | **Wildlife killed and injured** | Animals that died or were hurt *because of* conflict, by species and cause. Natural deaths, disease and poaching are excluded. |
| 8 | **Livestock predation** | What was lost, to which predator, and whether animals were inside or outside a boma. The map sizes each point by the number killed. |
| 9 | **Crop and infrastructure damage** | What was damaged, by what, how badly, how it changed over time, and where — a separate map for crops and for property. |
| 10 | **Retaliation** | How often retaliation against wildlife was threatened or carried out, and against which species. |

## Downloading the results

Open the **Files** tab. It lists the Word report and the incident CSV. Click
to download.

The charts and maps are not in that tab — they are written to the results
folder alongside them, and every one of them is also embedded in the Word
report, which is usually what you want to send on.

The results **folder** holds many more files than the Files tab shows — an HTML
file behind every chart and map, and a PNG of each one that went into the Word
report. That is normal. The Files tab lists the things meant for you to keep.

## How incidents are counted

Worth knowing before you quote a number to anyone.

**An incident is not the same as an event.** Rangers can group several events
— a crop raid, an injury and a livestock loss from the same elephant — into
one incident. *Total incidents* counts each such group once, and a standalone
event once. Everything else counts per event or per victim, so one incident
can account for several injured people. That is why the incident total and the
loss totals do not add up to each other.

**There is no "conflict" event type in EarthRanger.** An incident counts as
conflict based on the event *and* what its cause field says:

| Event type | Counts as conflict when |
|---|---|
| HWC Livestock Predation | always — the event type is the cause |
| Human Injury | Cause of injury = Human-wildlife conflict |
| Human Death | Cause = Human-wildlife conflict |
| Crop Damage | Cause of damage = Wildlife |
| Infrastructure Damage | Cause of damage = Wildlife |
| Animal Carcass | Type of Death = Conflict |
| Sick / Injured Animal | Type of Injury = Conflict |
| Poisoning | Suspected motive = HWC retaliation |

A crop damage record caused by livestock, or a carcass that died of disease, is
not counted. Every section applies the same test, so the headline total, the
species chart and the hotspot map always count the same records.

**"Species responsible" is not "species killed."** Sections 3 and 6 report the
animal that *caused* the incident. Section 7 reports the animal that *died or
was hurt*. An elephant can appear in both, for different reasons.

**Species names are standardised before counting.** The event forms spell the
same animal differently — `Baboon, Olive` on one form and `Olive Baboon` on
another, and Human Death lets rangers type the name freely. The workflow maps
these onto one name, so one elephant is one bar rather than three.

**'Unknown' and 'Not recorded' mean the field was left blank**, not that
something was investigated and came back unknown.

**Multi-select fields group as combinations.** Where a ranger ticked both
*Water Pipes* and *Water Tank*, you get a row reading `Water Pipes, Water Tank`
rather than one each — so you cannot add rows to get a per-item total.

## Privacy

Names, ID numbers, telephone numbers, dates of birth, ethnicity and tribe are
**never** included — not in a widget, not in the Word report, and not in the
downloadable CSV. The casualty record shows date, outcome, species, age, sex,
action taken and the event serial number, so an incident can be traced back in
EarthRanger without the file itself carrying personal details.

Treat the CSV as sensitive anyway: it is still a precise list of where and when
people were hurt.

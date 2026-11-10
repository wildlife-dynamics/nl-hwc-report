# Naibunga Lower Human-Wildlife Conflict Report — User Guide

This guide walks you through running the Naibunga Lower HWC Report, which reads
human-wildlife conflict events from EarthRanger and produces an interactive
dashboard and a Word report for a period you choose.

## Overview

Each run delivers:

- **A dashboard** — 36 widgets across 13 sections, with **one view per month**
  in the period. A dropdown at the top switches between months.
- **A Word report** (`naibunga_lower_hwc_report_<hash>.docx`) — the same
  material written out with headings, numbered tables and figures, ready to
  send or print.
- **One CSV per month** (`hwc_incidents_<hash>_<hash>.csv`) — every conflict
  incident in that month, one row each, for your own analysis.

The report answers, for the period: how many conflict incidents occurred and of
what kind, which species were responsible, where incidents cluster, who and
what was lost, how it was responded to, and how often retaliation against
wildlife was threatened or carried out.

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
3. Builds the charts, tables and maps, once per month.
4. Downloads the Word template and fills it in.
5. Writes everything to the results folder and assembles the dashboard.

A two-month run takes a few minutes. Most of that is rendering maps.

## Reading the dashboard

Use the dropdown at the top to switch months. Two widgets — *Conflict Incidents
per Month by Type* and *Incident Timeline* — deliberately ignore it and always
show the whole period, because their point is the comparison across months.

| # | Section | What it tells you |
|---|---|---|
| 1 | **Headline totals** | Eight cards: incidents, people injured, people killed, livestock killed, wildlife killed, wildlife injured, poisonings, retaliation events. Your top-line numbers for the month. |
| 2 | **Conflict type** | How the month's incidents split between predation, crop damage, infrastructure damage, human injury, human death and wildlife death. |
| 3 | **Species responsible** | Which animals caused conflict, and which kind. The cross-tab reads species down, conflict type across. |
| 4 | **Hotspots** | Every incident at its recorded location, coloured by type, plus a density map. Where points cluster is where to concentrate effort. |
| 5 | **Seasonality** | Incidents per month across the whole period, stacked by type. Shows when conflict rises and falls. |
| 6 | **People injured and killed** | Casualties by the species responsible, and a record of each one with the action taken. |
| 7 | **Wildlife killed and injured** | Animals that died or were hurt *because of* conflict, by species and cause. Natural deaths, disease and poaching are excluded. |
| 8 | **Livestock predation** | What was lost, to which predator, and whether animals were inside or outside a boma. The map sizes each point by the number killed. |
| 9 | **Crop and infrastructure damage** | What was damaged, by what, and how badly. |
| 10 | **Response** | What was done, grouped into categories. |
| 11 | **Retaliation** | How often retaliation against wildlife was threatened or carried out, and against which species. |
| 12 | **Incident timeline** | Every incident in time order with the gap since the previous one. Useful for spotting bursts. |
| 13 | **Data completeness** | How often key fields were left blank. Read this one first — it tells you how much to trust the rest. |

## Downloading the results

Open the **Files** tab. It lists the Word report and one CSV per month. Click to
download.

The results **folder** holds many more files than the Files tab shows — an HTML
file behind every chart and map, and a PNG of each one that went into the Word
report. That is normal. The Files tab lists the things meant for you to keep.

## How incidents are counted

Worth knowing before you quote a number to anyone.

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
something was investigated and came back unknown. Section 13 counts these.

**Multi-select fields group as combinations.** Where a ranger ticked both
*Water Pipes* and *Water Tank*, you get a row reading `Water Pipes, Water Tank`
rather than one each.

**One incident can appear in more than one response category** in Section 10,
because several actions can be recorded. Compare *Any action recorded* with
*Incidents* to see how often any response was logged at all. *Other /
unspecified* means an action was recorded that does not fit the named
categories — in practice the ranger chose "Other (specify in notes)", so the
detail is in the incident's notes.

## Privacy

Names, ID numbers, telephone numbers, dates of birth, ethnicity and tribe are
**never** included — not in a widget, not in the Word report, and not in the
downloadable CSV. The casualty record shows date, outcome, species, age, sex,
action taken and the event serial number, so an incident can be traced back in
EarthRanger without the file itself carrying personal details.

Treat the CSV as sensitive anyway: it is still a precise list of where and when
people were hurt.

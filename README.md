# lecture-datasets

Single source of truth for all datasets used in Datawrapper charts for lectures.
Every dataset is a folder with three files. Every CSV is reachable via a stable raw URL
that Datawrapper can link ("Link external dataset" → Option 1, Datawrapper server).

## Current contents

Initial setup: validator, CSV standard, templates and one **synthetic pipeline-test dataset**.
This is not yet the complete Digital Business Models lecture collection.

## Structure

```
lecture-datasets/
├── repo.config.json            # owner / repo / branch → used to build raw URLs
├── CSV-STANDARD.md             # the rules every dataset must pass
├── CATALOG.md                  # generated: all datasets + raw URLs (do not edit)
├── datasets/
│   ├── _template/              # copy this to start a new dataset
│   │   ├── data.csv
│   │   ├── spec.json           # chart spec (datawrapper-charts skill format)
│   │   └── meta.json           # provenance, license, lecture, chart ID
│   └── <course>/<Lnn>-<slug>/  # one folder per chart
├── scripts/validate.py         # checks standard + regenerates CATALOG.md
└── .github/workflows/validate.yml
```

## Workflow (per chart)

1. `cp -r datasets/_template datasets/<course>/L03-<slug>`
2. Fill `data.csv` → follow `CSV-STANDARD.md`.
3. Fill `meta.json` (source, license, retrieved date) and `spec.json` (action title, type).
4. `python scripts/validate.py` → fix until green; `CATALOG.md` updates automatically.
5. Commit + push. The GitHub Action re-validates.
6. Build the chart:
   - **Static (default):** paste/upload the CSV in Datawrapper, or
     `python push_chart.py datasets/.../spec.json` (datawrapper-charts skill).
   - **Linked:** Datawrapper → Upload → *Link external dataset* → paste the raw URL from `CATALOG.md`.
7. Write the Datawrapper chart ID into `meta.json` → `datawrapper_chart_id`.

## Rules that protect the setup

- **Public repo = public data.** Only published, anonymized or synthetic data. Never client material.
- **Paths are URLs.** Never rename or move a folder once a chart links to it — linked charts break silently.
- **Edit data here, not in Datawrapper.** Cell edits in Datawrapper step 2 get misaligned when rows change.
- **Linked charts stop refreshing 30 days after publishing.** Republish before the lecture if data changed.

# Evaluatietool Selectie

Dashboard that evaluates whether selection procedures in Dutch higher education predict student success. Users upload selection scores, a config file, and 1CHO student data. The tool shows whether students who scored higher at selection also performed better (progressed to year 2).

## Running

```bash
uv sync
uv run python app.py        # starts Dash at localhost:8050
uv run ruff format .         # format
uv run ruff check --fix .    # lint
```

There are no tests. Verify changes by running the app and loading demo data.

## Source files

| File | Lines | Role |
|---|---|---|
| `app.py` | ~2000 | Main Dash app. Layout, 18 callbacks, data loading, all four dashboard tabs. Entry point. |
| `rapport.py` | ~1040 | PDF report generation. Uses fpdf2 + kaleido. Called from app.py download button. |
| `config_wizard.py` | ~720 | Auto-detection of columns from uploaded Excel. Integrated into app.py via `registreer_callbacks`. |
| `transformatie.py` | ~240 | File parsing, config reading, data validation, wide-to-long transformation. |
| `shared.py` | ~27 | Shared constants and helpers used by both app.py and rapport.py. |

## Data flow

1. User uploads selectiedata.xlsx + config.xlsx + 1cho_data.csv (or loads demo data)
2. `transformatie.lees_config()` reads the config Excel (sheets: `instellingen`, `kolommen`)
3. `transformatie.parse_selectiedata()` reads the selection Excel using config metadata (sheet name, header row)
4. `transformatie.transformeer_naar_lang()` melts wide score columns into long format (`scores_df`)
5. `app.koppel_data()` merges 1CHO data with pivoted scores, computes z-scores and totaalscore, assigns groups
6. Both `df` (joined main data) and `scores_df` (long-format scores) are stored as JSON in `dcc.Store`
7. Callbacks deserialize and filter per tab

## The three groups

Students are categorized based on 1CHO enrollment data:

- **Niet gestart**: not in 1CHO at all. Either rejected or chose not to enroll.
- **Gestart, niet naar jaar 2**: enrolled in year 1 but no year 2 record. Dropped out or switched.
- **Doorgestroomd naar jaar 2**: enrolled in both year 1 and year 2. Successfully progressed.

Regression and VO analyses use only the latter two groups (students who actually started), because there is no outcome data for the "niet gestart" group.

## Dashboard tabs (app.py callbacks)

| Tab | Key callback | What it shows |
|---|---|---|
| Selectiescores | `update_scores_tab` | Boxplots per item per group, mean/SD table. Filters: instrument, criterium, item. |
| Samenhang | `update_samenhang_tab` | Correlation heatmap with Cohen 1988 interpretation, logistic regression table. |
| Demografisch | `update_demo_tab` | Stacked bars for cohort distribution, geslacht, herkomst (Nederland/niet-Nederland), vooropleiding. |
| VO-cijfer | `update_vo_tab` | Pearson correlations between selection scores and VO GPA, scatter plot. |

## PDF report (rapport.py)

`genereer_rapport(df, scores_df) -> bytes` produces a multi-section PDF:

1. Inleiding (explains groups and why some analyses use only 2)
2. Dataset overzicht (instruments, items, group counts)
3. Selectiescores per groep (boxplot, means table)
4. Samenhang en regressie (heatmap with Cohen interpretation, logistic regression)
5. Demografisch profiel (verdeling, geslacht, herkomst, vooropleiding with charts and tables)
6. VO-eindcijfer (Pearson correlations with strength labels, scatter)
7. Samenvatting (auto-generated bullet points)

### Kaleido performance

Kaleido 1.x spawns a new headless Chromium per `to_image()` call, taking ~4-5s each. With 7 charts that is ~30s. Parallelization was tried (ThreadPoolExecutor, multiprocessing) and failed: browser conflicts, "unclean kill" errors, Windows pickle issues. Kaleido 0.x (persistent browser, faster) has no Windows AMD64 wheels. The current approach renders sequentially with a loading spinner + toast notification for UX.

## Key constants and shared code (shared.py)

- `GROEP_VOLGORDE`: canonical group order list
- `GROEP_KLEUREN`: color map (gray/orange/green) for the three groups
- `CHART_BASE`: white background for all Plotly charts
- `shorten_item()`: strips " schaalscore", " Schaalscore", " (1-2-3)" from item names
- `sig_sym()` / `fmt_p()`: significance symbols and p-value formatting

## Config wizard (config_wizard.py)

Lets users skip the manual config Excel. Upload a selectiedata file, click "Of: config automatisch genereren", and the wizard detects:

- Which sheet contains data and where the header row is
- Which column is the student ID (keyword scan: studentnummer, aanvraagnummer, etc.)
- Which columns are numeric scores (filters out text, dates, rankings)
- Instrument grouping from column name prefixes
- Opleiding, instelling, and jaar from the filename

The user reviews everything in an editable DataTable, removes unwanted rows, renames instruments, then confirms. The resulting config dict is identical to what `lees_config()` returns, so the rest of the pipeline works unchanged.

All component IDs are prefixed `wiz-` to avoid collisions with dashboard components.

`exporteer_config_excel(config_dict)` writes a two-sheet Excel so the user can reuse the config without the wizard next time.

## Config file format

The config Excel has two sheets:

- **instellingen**: key-value pairs (koppel_id_kolom, opleiding, instellingscode, jaar, blad_naam, header_rij, totaalscore_kolom, etc.)
- **kolommen**: one row per score column with fields: kolom_naam, instrument, item, criterium

## Demo data

Two datasets in `data/demo/`:
- `biomed_aumc_2026/` (120 candidates, 10 items across 4 instruments)
- `bewegingswetenschappen_vu_2026/` (80 candidates)

Each contains: `selectiedata.xlsx`, `config.xlsx`, `1cho_data.csv`

To test the full pipeline from a script:
```python
import base64, pandas as pd
from pathlib import Path
from transformatie import lees_config, parse_selectiedata, transformeer_naar_lang
from app import koppel_data
from rapport import genereer_rapport

demo = Path("data/demo/biomed_aumc_2026")
uri = lambda p: f"data:application/octet-stream;base64,{base64.b64encode(p.read_bytes()).decode()}"
config = lees_config(uri(demo / "config.xlsx"))
scores_df = transformeer_naar_lang(parse_selectiedata(uri(demo / "selectiedata.xlsx"), config), config)
df = koppel_data(pd.read_csv(demo / "1cho_data.csv", sep=";"), scores_df)
pdf = genereer_rapport(df, scores_df)
```

## Project structure

```
scripts/
  maak_data.py          # generates demo 1CHO data from source files (dev-only)
  maak_template.py      # generates docs/config_template.xlsx
  eenmalig/             # one-time scripts, not part of the running tool
    maak_presentatie.py  # generates the PowerPoint presentation
    maak_fictief_*.py    # generates fictitious selectiedata for demos
    update_configs.py    # one-time config migration
    update_datawoordenboek.py

docs/
  data-handleiding.md    # explains expected data formats for end users
  config_template.xlsx   # empty config with cell-level instructions

data/
  demo/                  # shipped with repo, loaded by demo picker
    biomed_aumc_2026/
    bewegingswetenschappen_vu_2026/
  configs/               # gitignored, opleiding-specific configs for maak_data.py
  fictief/               # gitignored, intermediate output from fictief scripts
```

The `scripts/eenmalig/` scripts were used during project setup. They still work but are not needed for running or using the tool. `maak_data.py` requires source files that are gitignored (real/dummy selectiedata), so it only works on the developer's machine.

## Known gotchas

- **No .claudeignore**: the `data/` and `.venv/` directories are large. Don't glob or grep into them.
- **app.py stores data as JSON strings** in `dcc.Store`. Callbacks deserialize with `df_from_store()` and `pd.read_json(orient="split")`.
- **The config wizard** (`config_wizard.py`) registers its own callbacks via `registreer_callbacks(app)` at module level in app.py. It shares the upload components.
- **`bereken_pct()` in app.py** (line ~160) is a reusable groupby-pct helper. rapport.py does similar aggregations but handles them internally.
- **Herkomst mapping** (Nederland / niet-Nederland) is defined inline in both app.py and rapport.py. If changing the logic, update both.
- **fpdf2 SVG support** is limited. The NKO logo uses a PNG version (`assets/nko-logo.png`) for PDF rendering; the SVG (`assets/nko-logo.svg`) is only for the web dashboard.
- **statsmodels import** is done lazily inside `_run_regression()` because it is slow to import and only needed for the regression analysis.

## Multi-session coordination

Multiple Claude Code sessions work on this project in parallel. Rules:

- **config_wizard.py** is self-contained. Changes there don't conflict with app.py work.
- **app.py** is the highest-conflict file. Avoid large refactors unless you own it for the session. There is a pitch to split it up: https://github.com/cedanl/evaluatietool-voorbeeld/issues/15
- **rapport.py** and **shared.py** are owned by the rapport/dashboard session.
- **scripts/eenmalig/maak_presentatie.py** generates the PowerPoint. Update it when features change.
- Always check `git status` before committing. Another session may have staged or committed while you were working.
- Never commit data files, PDFs, or docx. The gitignore handles this, but double-check.

## Uncommitted work

<!-- Update this section when you commit or start new work. Other sessions will append here. -->

As of 2026-06-05:

- **rapport.py**: uncommitted rewrite by another session. Added inleiding section, Cohen 1988 correlation interpretation, herkomst demographics, PNG logo on cover, sequential chart rendering, logging, type hints.
- **assets/nko-logo.png**: new, untracked. Converted from SVG for PDF rendering.

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
| `cho_transform.py` | ~210 | Raw 1CHO handling. `transformeer_cho()` derives the doorstroom group from long-format enrollment rows; `bouw_ruwe_cho()` builds synthetic raw 1CHO for the data scripts. |
| `shared.py` | ~27 | Shared constants and helpers used by both app.py and rapport.py. |

## Data flow

1. User uploads selectiedata.xlsx + config.xlsx + 1cho_data.csv (or loads demo data)
2. `transformatie.lees_config()` reads the config Excel (sheets: `instellingen`, `kolommen`)
3. `transformatie.parse_selectiedata()` reads the selection Excel using config metadata (sheet name, header row)
4. `transformatie.transformeer_naar_lang()` melts wide score columns into long format (`scores_df`)
5. `cho_transform.transformeer_cho()` collapses the raw long-format 1CHO (one row per enrollment year) to one row per student and derives the doorstroom `groep`
6. `app.koppel_data()` merges that derived 1CHO with pivoted scores, computes z-scores and totaalscore, and fills non-matches with "Niet gestart"
7. Both `df` (joined main data) and `scores_df` (long-format scores) are stored as JSON in `dcc.Store`
8. Callbacks deserialize and filter per tab

## The four groups

Raw 1CHO data has no ready-made group column. It is enrollment data in long format (one row per student per `inschrijvingsjaar`). `cho_transform.transformeer_cho()` derives the group, mirroring the no-fairness-without-awareness pipeline (`R/transform_ev_data.R`, the `any(inschrijvingsjaar == eerste_jaar_aan_deze_opleiding_instelling + 1)` retentie check). Group derivation is per spell (studentnummer + opleiding + eerste_jaar), so a student with two programmes gets a separate outcome per programme. Priority: year-2 enrollment > diploma in cohort year > dropout.

- **Niet gestart**: not in 1CHO at all. Either rejected or chose not to enroll. Assigned in `koppel_data()` as the fillna for non-matches, not in `transformeer_cho()`.
- **Gestart, niet naar jaar 2**: has a first-year row but no `eerste_jaar + 1` row and no diploma.
- **Doorgestroomd naar jaar 2**: has an enrollment row in the year after the first year.
- **Gestart, diploma gehaald**: no year-2 row, but `diploma_behaald` is true in the cohort year. For one-year programmes (masters) where success means a diploma, not progression to year 2.

The group labels and the helper lists `GROEP_INGESCHREVEN` (all started) and `GROEP_SUCCES` (doorstroom or diploma) live in `shared.py`. Regression and VO analyses use `GROEP_INGESCHREVEN` (students who actually started) and treat `GROEP_SUCCES` as the positive outcome, so they work for both multi-year and one-year programmes.

The required raw 1CHO columns are `persoonsgebonden_nummer`, `inschrijvingsjaar`, and `eerste_jaar_aan_deze_opleiding_instelling` (see `cho_transform.RUWE_CHO_KOLOMMEN`). Optional passthrough columns: geslacht, herkomst, `hoogste_vooropleiding_omschrijving_vooropleiding` (shortened to VWO/HAVO/MBO/HO), gem_eindcijfer_vo, `diploma_behaald`.

The data scripts choose the outcome by `opleidingsfase`: masters (`"M"`, e.g. biomed demo) generate `diploma_behaald`; bachelors (`"B"`, e.g. bewegingswetenschappen demo) generate year-2 doorstroom.

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
from cho_transform import transformeer_cho
from app import koppel_data
from rapport import genereer_rapport

demo = Path("data/demo/biomed_aumc_2026")
uri = lambda p: f"data:application/octet-stream;base64,{base64.b64encode(p.read_bytes()).decode()}"
config = lees_config(uri(demo / "config.xlsx"))
scores_df = transformeer_naar_lang(parse_selectiedata(uri(demo / "selectiedata.xlsx"), config), config)
cho_df = transformeer_cho(pd.read_csv(demo / "1cho_data.csv", sep=";"))
df = koppel_data(cho_df, scores_df)
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

## Logistic regression: limitations and how we handle them

The samenhang tab runs a logistic regression predicting doorstroom (year 2) from all selection items. This is the most fragile part of the tool because selection datasets are small and the items have wildly different scales.

### Problem 1: Different scales

Selection items range from 1-3 ordinal ratings to 0-100 percentages to raw schaalscores. In a raw logistic regression, items on larger scales dominate the model simply because a 1-unit change means something different for each scale.

**How we handle it:** All items are z-score standardized before entering the model (`(x - mean) / sd`). This means coefficients and odds ratios express the effect of a 1-SD increase, which is comparable across scales. The dashboard explains this to the user in the collapsible "Uitleg regressietabel" section.

**What it does NOT solve:** Z-scores make coefficients comparable, but they don't fix non-linear relationships or heavily skewed distributions. An item where 90% of candidates score the same value has almost no variance after standardization and contributes little to the model regardless.

### Problem 2: Too few observations for the number of predictors

The "events per variable" (EPV) rule says you need at least 5-10 events (students in the smallest outcome group) per predictor. A dataset with 30 enrolled students and 15 who dropped out can support at most 3 predictors at EPV=5. With 12 selection items, you get unstable estimates and inflated odds ratios.

**How we handle it:** The code computes `max_predictoren = max(2, n_events // 5)`. If there are more items than that, it runs univariate logistic regressions for each item, ranks them by p-value, and keeps only the top `max_predictoren`. Dropped items are listed above the regression table so the user knows what was excluded and why.

**What it does NOT solve:** Even with selection, the model may be overfitted. With small samples, a single outlier can flip a coefficient from significant to not. We don't bootstrap or cross-validate. The results should be read as "suggestive patterns", not definitive evidence.

### Problem 3: Multicollinearity

Selection instruments often overlap. A "competentietest reflecteren" and a "competentietest stressbestendigheid" may correlate at r=0.8. In a joint model, neither appears significant because each explains variance the other already covers.

**How we handle it:** Before fitting, the code checks the matrix rank of the predictor matrix. If rank < number of columns, it iteratively removes the column with the highest pairwise correlation until the matrix is full rank. Removed items are reported as "Items niet meegenomen (overlap met andere items)".

**What it does NOT solve:** This only catches near-perfect collinearity (rank deficiency). High but not perfect correlations (r=0.7-0.8) still inflate standard errors and make individual p-values unreliable. The correlation heatmap on the same tab helps the user spot this.

### Problem 4: Missing data

Some items have missing values for a subset of candidates (optional modules, keuzevakken). Listwise deletion would throw away too many cases.

**How we handle it:** Items with >30% missing values are excluded entirely. For the remaining items, missing values are imputed with the column mean. This is conservative and slightly biases coefficients toward zero.

### Summary for developers

The regression output is useful for spotting patterns but should not be overinterpreted given typical sample sizes (50-150 enrolled students). The dashboard communicates this through the toelichting text and the pseudo R-squared. When changing the regression code, test with both demo datasets: biomed has 10 items and ~84 enrolled students (comfortable EPV), bewegingswetenschappen has fewer items but header_rij=3 and more missing data.

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

## Recent changes (2026-06-05, session A)

This session did the bulk of the multi-programme work:

- **Multi-programme support**: pipeline tested and working for FAR Leiden 2025/2026, Psychologie 2022/2026, plus two fictive datasets.
- **Config wizard**: auto-detects opleiding/instelling/jaar from filename. Opleiding/instelling/jaar fields live in the wizard (not separate inputs). score_type removed from config format entirely (4 columns: kolom_naam, instrument, item, criterium).
- **Upload flow**: split into validate + explicit "Open dashboard" button. Validates studentnummer overlap between selectiedata and 1CHO. Shows opleiding/instelling/jaar from config in validation feedback.
- **Cascading filters on scores tab**: instrument/criterium/item dropdowns are linked. Selecting an instrument narrows criterium and item options. Impossible combinations auto-reset.
- **Single-item boxplot**: when one item is selected (via filter or because only one item matches), shows group-level boxplot with correct y-axis scale.
- **Samenhang tab filters**: own instrument/criterium dropdowns. Filters only affect the correlation matrix, not the regression.
- **Regression robustness**: items with >30% missing data excluded, multicollinear items auto-removed (matrix rank check). Both dashboard and PDF report show which items were dropped and why.
- **Toelichtingen**: all explanatory text rewritten for a broad audience. Collapsible interpretation guides for correlation (Cohen 1988), regression table, and VO-cijfer. Demographic tab explains 1CHO data origin and how doorstroom is determined.
- **Fictive demo data**: BioMed AUMC 2026 (master, 120 candidates, 90 columns) and Bewegingswetenschappen VU 2026 (bachelor, 80 candidates, 37 columns, header_rij=3). Demo picker shows only fictive data.
- **Pitch created**: [#14](https://github.com/cedanl/evaluatietool-voorbeeld/issues/14) Diploma as alternative outcome measure for 1-year masters.

## Recent changes (2026-06-05, audit session)

This session audited the full codebase for bugs, dead code, and data safety. All fixes are committed.

### Bugs fixed
- **Z-score crash in koppel_data()**: `lambda s: ... if s.std() > 0 else 0` returned scalar 0, which broke `mean(axis=1)`. Fixed to return `pd.Series(0, index=s.index)`.
- **int("") crash in transformatie.py**: `int(config.get("header_rij", 1))` crashes when header_rij is empty string `""`. Fixed to `int(config.get("header_rij") or 1)`.
- **split without maxsplit**: `contents.split(",")` in `_decode_upload()` could split base64 data containing commas. Fixed to `split(",", 1)`.
- **Early return wiped validation state**: `valideer_uploads` returned `""` for store components instead of `dash.no_update`, wiping previously loaded data on partial re-uploads. Fixed.
- **Double lees_config call**: config was parsed twice in the upload callback. Refactored to parse once with a `config = None` guard.

### Dead code removed
- `get_score_cols()`, `col_to_label()`, `score_opties_uit_df()` in app.py (unused after filter refactor)
- `detecteer_bladen()` in config_wizard.py (never called)
- `item_opties` variable in app.py (superseded by cascading filters)

### Cleanup
- `python-pptx` removed from runtime dependencies (only used by scripts/eenmalig/)
- Extracted `bereken_pct()` helper in app.py to replace 4 inline groupby-percentage calculations
- `kandidaat_id_kolom` renamed to `koppel_id_kolom` in maak_template.py to match what transformatie.py expects

### Data safety audit
- Verified gitignore blocks all PII-containing files (selectiedata with names/emails/student numbers)
- Confirmed data/demo/ only contains fictive data generated by scripts/eenmalig/maak_fictief_*.py
- Fixed over-broad gitignore that was blocking config.xlsx and demo data from being committed
- Added path-specific gitignore rules instead of global `*.csv` / `*.xlsx` blocks

## Known issues (not yet fixed)

These were identified during the audit but left unfixed. Pick them up when relevant.

### Code quality
- **rapport.py duplicates analysis logic**: regression, Pearson-r, and demographic aggregations are reimplemented separately from app.py. Extracting shared analysis functions would prevent drift between dashboard and PDF.
- **Silent except blocks in config_wizard.py**: callbacks at lines ~596 and ~641 swallow all exceptions with bare `except Exception`. Should at minimum log the error.
- **detecteer_totaalscore second loop too broad**: matches any column containing "totaal" in the name, which can pick up unrelated columns.
- **Hardcoded group strings**: `"Niet gestart"`, `"Gestart, niet naar jaar 2"`, `"Doorgestroomd naar jaar 2"` appear as raw strings throughout app.py instead of referencing `GROEP_VOLGORDE` from shared.py.
- **Large callbacks**: `update_samenhang_tab` (158 lines) and `update_vo_tab` (140 lines) do a lot of work inline. Splitting data prep from layout would improve readability.
- **No encoding fallback**: `parse_csv_or_excel()` in transformatie.py decodes CSV as utf-8 only. Dutch institutional files sometimes use latin-1 or cp1252.

### Uncommitted work from other sessions

As of 2026-06-05:

- **app.py + rapport.py**: regression z-score standardization (uncommitted, from session A). Note: the `else 0` in `lambda s: (s - s.mean()) / s.std() if s.std() > 0 else 0` returns a scalar. This is the same pattern that caused the koppel_data z-score crash. Should be `pd.Series(0, index=s.index)` for safety.
- **assets/nko-logo.png**: untracked. Converted from SVG for PDF rendering. Needs to be committed.

# Evaluatietool Selectie

Dashboard that evaluates whether selection procedures in Dutch higher education predict student success. Users upload selection scores, a config file, and 1CHO student data. The tool shows whether students who scored higher at selection also performed better (progressed to year 2).

## Running

```bash
uv sync
uv run python app.py        # starts Dash at localhost:8050
uv run ruff format .         # format
uv run ruff check --fix .    # lint
```

Tests live in `tests/` (pytest). Run with `uv run pytest -q`. Still verify UI changes by running the app and loading demo data, since the tests cover the data pipeline, not the Dash callbacks.

## Source files

app.py was split into modules per responsibility (pitch [#15](https://github.com/cedanl/selectie-evaluatietool/issues/15)). Each tab module and uploads.py exports `maak_layout()` and/or `registreer_callbacks(app)`, the same pattern config_wizard.py uses. app.py only composes the layout and wires the callbacks.

| File | Lines | Role |
|---|---|---|
| `app.py` | ~120 | App init, layout composition, `registreer_callbacks` wiring, the embed-via-URL callback, server start. Entry point. |
| `helpers.py` | ~360 | Shared app-level helpers: `koppel_data`, `bouw_data_stores` (runs parse→transform→join, shared by the upload and demo load paths), `df_from_store`, `_laad_demodata`, `TABLE_STYLE`, `GROEPEER_OPTIES`, the groep-/kleur-helpers (`_scores_per_groep`, `_aantallen_per_groep`, `_groep_tabel_stijl`, `_meng_met_wit`), `_bereken_model_stats`, `DEMO_DATASETS`. |
| `uploads.py` | ~450 | Upload overlay + sidebar layout and the upload/validation/demodata-load/cohort/download callbacks. |
| `tabs/intro.py` | ~190 | "Introductie"-tab: static, accessible welcome/context page. No callbacks (kept out of the `registreer_callbacks` loop). First tab, active by default. Group labels/colors come from `shared.GROEP_KLEUREN`. |
| `tabs/bevindingen.py` | ~315 | "Wat valt op"-tab: layout + `update_bevindingen`. |
| `tabs/scores.py` | ~430 | Selectiescores-tab: layout + cascading score-filters + `update_scores_tab`. |
| `tabs/demografie.py` | ~200 | Demografie-tab: layout + `update_demografie_tab`. |
| `tabs/verschiltoets.py` | ~165 | Verschiltoets-tab: layout + `update_verschiltoets_tab`. |
| `tabs/correlatie.py` | ~245 | Correlatie-tab: layout + `update_correlatie_tab` + the data-change callback that fills the correlatie filters and the app-subtitle. |
| `tabs/regressie.py` | ~395 | Regressie-tab: layout + `update_regressie_tab`. |
| `rapport.py` | ~960 | PDF report generation. Uses fpdf2 + kaleido. Called from uploads.py download button. |
| `config_wizard.py` | ~895 | Auto-detection of columns from uploaded Excel. Wired in app.py via `registreer_callbacks`. |
| `transformatie.py` | ~240 | File parsing, config reading, data validation, wide-to-long transformation. |
| `cho_transform.py` | ~240 | Raw 1CHO handling. `transformeer_cho()` derives the doorstroom group from long-format enrollment rows; `bouw_ruwe_cho()` builds synthetic raw 1CHO for the data scripts. |
| `shared.py` | ~850 | Shared constants and analysis functions used by the tabs and rapport.py (perspectieven, effectgroottes, `vergelijk_succes_per_item`, `toets_verschil_per_item`, `bereken_univariaat`, `chi2_per_dimensie`, `genereer_bevindingen`, demografie-helpers). |

## Data flow

1. User uploads selectiedata.xlsx + config.xlsx + 1cho_data.csv (or loads demo data)
2. `transformatie.lees_config()` reads the config Excel (sheets: `instellingen`, `kolommen`)
3. `transformatie.parse_selectiedata()` reads the selection Excel using config metadata (sheet name, header row)
4. `transformatie.transformeer_naar_lang()` melts wide score columns into long format (`scores_df`)
5. `cho_transform.transformeer_cho()` collapses the raw long-format 1CHO (one row per enrollment year) to one row per student and derives the doorstroom `groep`
6. `helpers.koppel_data()` merges that derived 1CHO with pivoted scores, computes z-scores and totaalscore, and fills non-matches with "Niet gestart"
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

The data scripts choose the outcome by `opleidingsfase`: masters (`"M"`, e.g. the Leiden/Farmacie demo) generate `diploma_behaald`; bachelors (`"B"`, e.g. the Radboud/Psychologie demo) generate year-2 doorstroom.

## Dashboard tabs

Each tab is its own module under `tabs/`, with `maak_layout()` for the layout and `registreer_callbacks(app)` for the callbacks listed below.

| Tab | Module | Key callback | What it shows |
|---|---|---|---|
| Introductie | `tabs/intro.py` | (none) | Static, accessible welcome page: what the tool answers, how it works in three steps, the groups (gestart-zonder-vervolg vs studiesucces), and a per-tab guide. First tab, active by default. |
| Wat valt op | `tabs/bevindingen.py` | `update_bevindingen` | Auto-generated findings from `shared.genereer_bevindingen`. Every line follows from a measured effect size or p-value, nothing invented. |
| Selectiescores | `tabs/scores.py` | `update_scores_tab` | Boxplots per item per group, mean/SD table. "Groepeer op" dropdown: gestart, doorstroom, or a demographic dimension (geslacht, vooropleiding). Filters: instrument, criterium, item, schaal/bereik (cascading, via `update_score_filters`). |
| Demografie | `tabs/demografie.py` | `update_demografie_tab` | Per background dimension (geslacht, vooropleiding), crosstab of the dimension against doorstroom outcome. |
| Verschiltoets | `tabs/verschiltoets.py` | `update_verschiltoets_tab` | Per-item significance test (Mann-Whitney for doorstroom, Kruskal-Wallis for demographic dimensions) with effect size and p-value. |
| Correlatie | `tabs/correlatie.py` | `update_correlatie_tab` | Inter-item correlation heatmap with Cohen 1988 interpretation. Own instrument/criterium filters (filled by `update_filters_on_data_change`, which also sets the app-subtitle). |
| Regressie | `tabs/regressie.py` | `update_regressie_tab` | Univariate + joint logistic regression predicting study success (doorstroom or diploma). |

## PDF report (rapport.py)

`genereer_rapport(df, scores_df) -> bytes` produces a multi-section PDF:

1. Inleiding (explains the chosen perspective and the two groups compared)
2. Dataset overzicht (instruments, items, group counts)
3. Selectiescores per groep (boxplots per scale, means table, per-item verschiltoets)
4. Samenhang en regressie (correlation heatmap with Cohen interpretation, logistic regression)
5. Selectiescores naar achtergrond (per-item Kruskal-Wallis verschiltoets per demographic dimension: geslacht, vooropleiding)
6. Conclusies (auto-generated bullet points from `genereer_bevindingen`)

### Kaleido performance

Kaleido 1.x spawns a new headless Chromium per `to_image()` call, taking ~4-5s each. With 7 charts that is ~30s. Parallelization was tried (ThreadPoolExecutor, multiprocessing) and failed: browser conflicts, "unclean kill" errors, Windows pickle issues. Kaleido 0.x (persistent browser, faster) has no Windows AMD64 wheels. The current approach renders sequentially with a loading spinner + toast notification for UX.

## Key constants and shared code (shared.py)

- `GROEP_VOLGORDE`: canonical group order list
- `GROEP_KLEUREN`: color map (gray/orange/green) for the three groups
- `CHART_BASE`: white background for all Plotly charts
- `shorten_item()`: strips " schaalscore", " Schaalscore", " (1-2-3)" from item names
- `sig_sym()` / `fmt_p()`: significance symbols and p-value formatting

## Config wizard (config_wizard.py)

Lets users skip the manual config Excel. The wizard lives in the upload overlay but opens as its own **full-screen page** (`wiz-overlay`, styled `.wiz-overlay`/`.wiz-card`) via the "Config automatisch genereren" button (`wiz-open-btn`); a red "Sluiten" button (`wiz-close-btn`) closes it. It is a single flat page (not stepwise); `toon_wizard` toggles the overlay's display. After uploading a selectiedata file it detects:

- Which sheet contains data and where the header row is
- Which column is the student ID (keyword scan: studentnummer, aanvraagnummer, etc.)
- Which columns are numeric scores (filters out text, dates, rankings)
- Instrument grouping from column name prefixes
- A suggested scale per score column (`_raad_schaal`, rounded to a tidy range like 1-7 or 0-100)
- Opleiding, instelling, and jaar from the filename

`detecteer_alle_kolommen` returns **one row per column** in the sheet, with `_meenemen` pre-set True for the detected score columns and False for the rest (ID/text/date columns, with blank instrument/item/schaal). The user reviews everything in an editable DataTable where inclusion is a **checkbox per row** (`row_selectable="multi"`); the column name is read-only, instrument/item/criterium/schaal are editable. `bevestig_config` writes **all** rows to the config, each with `meenemen` set from the checkbox, so the config carries every column. `exporteer_config_excel` writes the `meenemen` column. The pipeline (via `meegenomen_kolommen`) analyzes only the checked rows.

All component IDs are prefixed `wiz-` to avoid collisions with dashboard components.

`exporteer_config_excel(config_dict)` writes a two-sheet Excel so the user can reuse the config without the wizard next time.

## Config file format

The config Excel has two sheets:

- **instellingen**: key-value pairs (koppel_id_kolom, opleiding, instellingscode, jaar, blad_naam, header_rij, totaalscore_kolom, etc.)
- **kolommen**: one row per **every** column in the selection sheet, with fields: `meenemen` (boolean, first column), kolom_naam, instrument, item, criterium, schaal. `meenemen` (TRUE/FALSE, also Ja/Nee, 1/0) flags which columns are score items; only those are analyzed. `lees_config` keeps all rows with a `meenemen` key, and `transformatie.meegenomen_kolommen()` / the pipeline filter on it (`transformeer_naar_lang`, `valideer_config`). `schaal` is the score range (e.g. `1-7`, `0-100`). Backward compatible: an older config whose first column is `kolom_naam` (no `meenemen`) is read with every row defaulting to meenemen=True.

## Demo data

Two datasets in `data/demo/`, deliberately different in shape so the demos don't look alike. Each mirrors a real (gitignored) source file:
- `demo_leiden_2026/` (Farmacie master, Universiteit Leiden, 140 candidates, 70 enrolled). Mirrors `dummy data selectie FAR Leiden 2025`: a master selection on sheet "2 Master beoordelingen" with a single header row (header_rij=1). Bachelordiploma assessment (gemiddeld cijfer + studietempo) plus two assessors (B1, B2) scoring NL documents, gesprek/schrijfopdracht and the selection interview. The `C_*_Sc_*` point columns add up to subtotals and `C_Sc_Totaal`. Because it is a master, the outcome is `diploma_behaald`, not year-2 doorstroom. 11 config items across instruments Bachelordiploma and Gesprek.
- `demo_radboud_2026/` (Psychologie bachelor, Radboud Universiteit, 200 candidates, 70 enrolled). Mirrors `2026-2027 Totaalscores Psychologie (dummy)`: schooldiploma kernvakken + combinatiecijfer + matchingsvragenlijst, header_rij=3. Keuzevakken are in the raw Excel but not config items, only via the combinatiecijfer. Outcome is year-2 doorstroom. 7 config items.

Each contains: `selectiedata.xlsx`, `config.xlsx`, `1cho_data.csv`

To test the full pipeline from a script:
```python
import base64, pandas as pd
from pathlib import Path
from transformatie import lees_config, parse_selectiedata, transformeer_naar_lang
from cho_transform import transformeer_cho
from helpers import koppel_data
from rapport import genereer_rapport

demo = Path("data/demo/demo_leiden_2026")
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
    maak_fictief_*.py    # generates fictitious selectiedata for demos (demo_leiden, demo_radboud)
    update_configs.py    # one-time config migration
    update_datawoordenboek.py

docs/
  data-handleiding.md    # explains expected data formats for end users
  config_template.xlsx   # empty config with cell-level instructions

data/
  demo/                  # shipped with repo, loaded by demo picker
    demo_leiden_2026/
    demo_radboud_2026/
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

The regression output is useful for spotting patterns but should not be overinterpreted given typical sample sizes (50-150 enrolled students). The dashboard communicates this through the toelichting text and the pseudo R-squared. When changing the regression code, test with both demo datasets: demo_leiden (Farmacie master, 11 items, 70 enrolled, header_rij=1, diploma outcome) and demo_radboud (Psychologie bachelor, 7 items, 70 enrolled, header_rij=3, doorstroom outcome). They differ in shape on purpose, so passing both exercises both the master/diploma and bachelor/doorstroom paths.

## Known gotchas

- **No .claudeignore**: the `data/` and `.venv/` directories are large. Don't glob or grep into them.
- **The data stores hold JSON strings** in `dcc.Store` (data-store, scores-store). Tab callbacks deserialize with `helpers.df_from_store()` and `pd.read_json(orient="split")`.
- **The config wizard** (`config_wizard.py`) registers its own callbacks via `registreer_callbacks(app)`, wired in app.py. It shares the upload components with uploads.py.
- **fpdf2 SVG support** is limited. The NKO logo uses a PNG version (`assets/nko-logo.png`) for PDF rendering; the SVG (`assets/nko-logo.svg`) is only for the web dashboard.
- **statsmodels import** is done lazily inside the regression code (`rapport._run_regression()`, `helpers._bereken_model_stats()`, `shared.bereken_univariaat()`, `tabs/regressie.py`) because it is slow to import and only needed for regression.

## Multi-session coordination

Multiple Claude Code sessions work on this project in parallel. Rules:

- **config_wizard.py** is self-contained. Changes there don't conflict with other work.
- **app.py** is now small (layout composition + wiring only). Tab work is isolated per `tabs/*.py` module, so two sessions on different tabs no longer conflict. Shared helpers live in helpers.py; touching those is the higher-conflict area now. (Pitch [#15](https://github.com/cedanl/selectie-evaluatietool/issues/15) to split app.py is implemented.)
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
- **Fictive demo data**: an early master + bachelor pair, later replaced by the current `demo_leiden_2026` (Farmacie master) and `demo_radboud_2026` (Psychologie bachelor). The demo picker shows only fictive data.
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

## Recent changes (2026-06-25, accessibility session)

Focused on making the tool clearer for non-technical users. All committed.

- **Introductie tab** (`tabs/intro.py`): new static, accessible welcome page, first tab and active by default. Explains what the tool answers, three steps, the groups, and a per-tab guide. No callbacks, so it stays out of the `registreer_callbacks` loop. Group labels/colors come from `shared.GROEP_KLEUREN`. The intro compares only started students (gestart-zonder-vervolg vs studiesucces); "Niet gestart" is not shown as a comparison group.
- **Config wizard is now a flat full-screen page** (was an inline collapse, briefly a stepwise flow). Opened by a clear outlined "Config automatisch genereren" button, closed by a red "Sluiten" button. The explanation is rewritten around the build-up of a selection procedure (instruments → items/criteria → scores → linking column).
- **Wizard column table uses checkboxes** (`row_selectable="multi"`) instead of a Meenemen-dropdown; the column name is read-only.
- **Schaal field added** to the config: a per-column range like `1-7`/`0-100`. The wizard auto-suggests it via `_raad_schaal` (rounds the observed max up to a tidy bound 3/5/7/10/20/25/50/100 or tens; lower bound 0 or 1). `lees_config`/`exporteer_config_excel` read/write it; older four-column configs still load.
- **`bouw_data_stores` helper** (helpers.py) runs the parse→transform→join pipeline once, shared by the upload and demo load paths to prevent drift.
- **"Univariate regressie" relabeled** to "Elk onderdeel apart" in the Wat valt op tab.
- **Configuratie tab was built and then removed** at the user's request, along with its `config-store`/`raw-selectie-store`/`raw-cho-store` stores. Don't re-add those stores unless that feature comes back.

## Known issues (not yet fixed)

These were identified during the audit but left unfixed. Pick them up when relevant.

### Code quality
- **rapport.py partly duplicates analysis logic**: the joint logistic regression (`_run_regression`) is still implemented separately from app.py. Most other analysis (univariate regression, per-item verschiltoets, findings) now lives in shared.py and is reused by both, which prevents drift.
- **Silent except blocks in config_wizard.py**: the detection callbacks (`detecteer_blad_en_header`, `detecteer_kolommen`) swallow all exceptions with bare `except Exception`. Should at minimum log the error. Several broad catches in rapport.py and tabs/regressie.py do the same.
- **detecteer_totaalscore second loop too broad**: matches any column containing "totaal" in the name, which can pick up unrelated columns.
- **Large callbacks**: `update_regressie_tab` and `update_verschiltoets_tab` still do a lot of work inline. Splitting data prep from layout would improve readability. (The old `update_samenhang_tab`/`update_vo_tab` were already split: Samenhang became the Correlatie + Regressie tabs and the VO-cijfer tab was removed.)
- **No encoding fallback**: `parse_csv_or_excel()` in transformatie.py decodes CSV as utf-8 only. Dutch institutional files sometimes use latin-1 or cp1252.

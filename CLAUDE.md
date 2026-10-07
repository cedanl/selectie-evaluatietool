# Evaluatietool Selectie

Dashboard that evaluates whether selection procedures in Dutch higher education predict student success. Users upload selection scores, a config file, and 1CHO student data. The tool shows whether students who scored higher at selection also performed better (progressed to year 2).

## Running

```bash
uv sync
uv run python app.py        # starts Dash at localhost:8050 (DASH_DEBUG=1 for the Werkzeug debugger; off by default)
uv run ruff format .         # format
uv run ruff check --fix .    # lint
```

Tests live in `tests/` (pytest). Run with `uv run pytest -q`. Still verify UI changes by running the app and loading demo data, since the tests cover the data pipeline, not the Dash callbacks.

## Source files

The code is split into modules per responsibility. Each tab module and uploads.py exports `maak_layout()` and/or `registreer_callbacks(app)`, the same pattern config_wizard.py uses. app.py only composes the layout and wires the callbacks.

| File | Role |
|---|---|
| `app.py` | App init, layout composition, `registreer_callbacks` wiring, the embed-via-URL callback, server start. Entry point. |
| `helpers.py` | Shared app-level helpers: `koppel_data`, `bouw_data_stores` (runs parse→transform→join, shared by the upload and demo load paths), `df_from_store`, `_laad_demodata`, `TABLE_STYLE`, `GROEPEER_OPTIES`, the groep-/kleur-helpers (`_scores_per_groep`, `_aantallen_per_groep`, `_groep_tabel_stijl`, `_meng_met_wit`), `DEMO_DATASETS` (`DEMO_DIR` is resolved relative to `helpers.py`, not the working directory). |
| `bestandsopslag.py` | Server-side storage for large 1CHO uploads: a Flask route the browser streams the file to (`assets/grote_upload.js`), returning a token the callbacks use instead of a base64 string. |
| `uploads.py` | Upload overlay + sidebar layout and the upload/validation/demodata-load/cohort/download callbacks. |
| `tabs/intro.py` | "Introductie"-tab: static, accessible welcome/context page. No callbacks (kept out of the `registreer_callbacks` loop). First tab, active by default. Group labels/colors come from `shared.GROEP_KLEUREN`. |
| `tabs/bevindingen.py` | "Wat valt op"-tab: layout + `update_bevindingen`. |
| `tabs/scores.py` | Selectiescores-tab: layout + cascading score-filters + `update_scores_tab`. |
| `tabs/demografie.py` | Demografie-tab: layout + `update_demografie_tab`. |
| `tabs/verschiltoets.py` | Verschiltoets-tab: layout + `update_verschiltoets_tab`. |
| `tabs/correlatie.py` | Correlatie-tab: layout + `update_correlatie_tab` + the data-change callback that fills the correlatie filters and the app-subtitle. |
| `tabs/regressie.py` | Regressie-tab: layout + `update_regressie_tab`. |
| `rapport.py` | PDF report generation. Uses fpdf2 + kaleido. Called from uploads.py download button. |
| `config_wizard.py` | Auto-detection of columns from uploaded Excel. Wired in app.py via `registreer_callbacks`. |
| `transformatie.py` | File parsing, config reading, data validation, wide-to-long transformation. |
| `cho_transform.py` | Raw 1CHO handling. `transformeer_cho()` derives the doorstroom group from long-format enrollment rows; `bouw_ruwe_cho()` builds synthetic raw 1CHO for the data scripts. |
| `shared.py` | Shared constants and analysis functions used by the tabs and rapport.py (perspectieven, effectgroottes, `vergelijk_succes_per_item`, `toets_verschil_per_item`, `bereken_univariaat`, `chi2_per_dimensie`, `genereer_bevindingen`, demografie-helpers). |

## Data flow

1. User uploads selectiedata.xlsx + config.xlsx + 1cho_data.csv (or loads demo data)
2. `transformatie.lees_config()` reads the config Excel (sheets: `instellingen`, `kolommen`)
3. `transformatie.parse_selectiedata()` reads the selection Excel using config metadata (sheet name, header row)
4. `transformatie.transformeer_naar_lang()` melts wide score columns into long format (`scores_df`)
5. `cho_transform.transformeer_cho()` collapses the raw long-format 1CHO (one row per enrollment year) to one row per student and derives the doorstroom `groep`
6. `helpers.koppel_data()` builds one row per candidate (plus selection metadata), merges the derived 1CHO onto it, and fills non-matches with "Niet gestart". The scores themselves stay in the long-format `scores_df`
7. Both `df` (joined main data) and `scores_df` (long-format scores) are stored as JSON in `dcc.Store`
8. Callbacks deserialize and filter per tab

## The four groups

Raw 1CHO data has no ready-made group column. It is enrollment data in long format (one row per student per `inschrijvingsjaar`). `cho_transform.transformeer_cho()` derives the group, mirroring the no-fairness-without-awareness pipeline (`R/transform_ev_data.R`, the `any(inschrijvingsjaar == eerste_jaar_aan_deze_opleiding_instelling + 1)` retentie check). Group derivation is per spell (studentnummer + opleiding + eerste_jaar), so a student with two programmes gets a separate outcome per programme. Priority: year-2 enrollment > diploma in cohort year > dropout.

- **Niet gestart**: not in 1CHO at all. Either rejected or chose not to enroll. Assigned in `koppel_data()` as the fillna for non-matches, not in `transformeer_cho()`.
- **Gestart, niet naar jaar 2**: has a first-year row but no `eerste_jaar + 1` row and no diploma.
- **Doorgestroomd naar jaar 2**: has an enrollment row in the year after the first year.
- **Gestart, diploma gehaald**: no year-2 row, but `diploma_behaald` is true on the cohort-year row (`inschrijvingsjaar == eerste_jaar`; a diploma flagged on a later row does not count). For one-year programmes (masters) where success means a diploma, not progression to year 2.

The group labels and the helper lists `GROEP_INGESCHREVEN` (all started) and `GROEP_SUCCES` (doorstroom or diploma) live in `shared.py`. Regression and VO analyses use `GROEP_INGESCHREVEN` (students who actually started) and treat `GROEP_SUCCES` as the positive outcome, so they work for both multi-year and one-year programmes.

1CHO columns fall into three groups:
- **Structurally required** (`cho_transform.RUWE_CHO_KOLOMMEN`, needed to derive the group): `persoonsgebonden_nummer`, `inschrijvingsjaar`, `eerste_jaar_aan_deze_opleiding_instelling`. `transformeer_cho` raises if missing.
- **Required for the analyses** (`cho_transform.VEREISTE_DEMO_KOLOMMEN`): `geslacht` and `hoogste_vooropleiding_omschrijving_vooropleiding` (shortened to VWO/HAVO/MBO/HO). The demografie- and eerlijkheidsanalyses need these, so the upload flow blocks opening the dashboard if they're missing (`ontbrekende_demografie_kolommen`, checked in `uploads.valideer_uploads`). They're enforced at the validation layer, not in `transformeer_cho`, so group-derivation still works without them (e.g. in the data scripts).
- **Conditional / optional passthrough**: `diploma_behaald` is master-only (one-year programmes; bachelors have no diploma column and use year-2 doorstroom), so it is **not** universally required. `opleiding`, `instellingscode` pass through if present.

**1cijferho output is read directly** (`cho_transform.normaliseer_1cijferho`, applied in `bestandsopslag.lees_cho_bestand`). The EV output of [1cijferho](https://github.com/cedanl/1cijferho) (preset "Evaluatietool Selectie", file `EV*_enriched.csv` or `_decoded.csv`) keeps DUO's number in `persoonsgebonden_nummer` and adds the institution's number as `studentnummer` when run with a BSN mapping file; the adapter makes `studentnummer` the join key. It also derives `diploma_behaald` for master-phase rows (`opleidingsfase_actueel`/`opleidingsfase` in M/master) as `inschrijvingsjaar - diplomajaar in {0, 1}`. Per the DUO file description, inschrijvingsjaar T runs Sep T to Aug T+1 but diplomajaar T runs Oct T to Sep T+1, so a diploma from September T has diplomajaar T-1. Combined with the cohort-row rule in `transformeer_cho` this means "diploma between September of the start year and September of the next year". Don't simplify to equality: that drops September diplomas. Bachelors get no diploma column. The plain `EV*.csv` lacks the decoded vooropleiding and programme name, so upload blocks on the missing demographic column and points to `_enriched.csv`. The README walks users through this end to end.

Robustness: studentnummers are normalized on both sides (`transformatie.normaliseer_studentnummer`: int/float/text → trimmed string, `123.0` → `123`) so the selectiedata↔1CHO join and the upload overlap check don't fail on type/format mismatches. Year columns are coerced with `pd.to_numeric` and `transformeer_cho` raises if a year column has no valid values; `diploma_behaald` is parsed with `transformatie._parse_bool` (so a text `"False"`/`"Nee"` is not silently truthy).

The data scripts choose the outcome by `opleidingsfase`: masters (`"M"`, e.g. the Leiden/Farmacie demo) generate `diploma_behaald`; bachelors (`"B"`, e.g. the Radboud/Psychologie demo) generate year-2 doorstroom.

## Dashboard tabs

Each tab is its own module under `tabs/`, with `maak_layout()` for the layout and `registreer_callbacks(app)` for the callbacks listed below.

| Tab | Module | Key callback | What it shows |
|---|---|---|---|
| Introductie | `tabs/intro.py` | (none) | Static, accessible welcome page: what the tool answers, how it works in three steps, the groups (gestart-zonder-vervolg vs studiesucces), and a per-tab guide. First tab, active by default. |
| Wat valt op | `tabs/bevindingen.py` | `update_bevindingen` | Auto-generated findings from `shared.genereer_bevindingen`. Every line follows from a measured effect size or p-value, nothing invented. |
| Selectiescores | `tabs/scores.py` | `update_scores_tab` | Boxplots per item per group, mean/SD table. "Groepeer op" dropdown: gestart, doorstroom, or a demographic dimension (geslacht, vooropleiding). Filters: instrument, criterium, item, schaal/bereik (cascading, via `update_score_filters`). |
| Demografie | `tabs/demografie.py` | `update_demografie_tab` | Per background dimension (geslacht, vooropleiding), crosstab of the dimension against doorstroom outcome. |
| Verschiltoets | `tabs/verschiltoets.py` | `update_verschiltoets_tab` | Per-item significance test (Mann-Whitney for doorstroom, Kruskal-Wallis for demographic dimensions) with effect size, raw p and Benjamini-Hochberg-corrected p (see "Multiple testing" below). |
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
- `GROEP_KLEUREN`: color map (gray/orange/green/blue) for the four groups
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
- **kolommen**: one row per **every** column in the selection sheet, with fields: `meenemen` (boolean, first column), kolom_naam, instrument, item, criterium, schaal. `meenemen` (TRUE/FALSE, also Ja/Nee, 1/0) flags which columns are score items; only those are analyzed. `lees_config` keeps all rows with a `meenemen` key, and `transformatie.meegenomen_kolommen()` / the pipeline filter on it (`transformeer_naar_lang`, `valideer_config`). `schaal` is the score range (e.g. `1-7`, `0-100`); it is documentation only, the charts derive their axis range from the observed scores (`shared.schaal_grenzen`/`schaal_bucket`). `totaalscore_kolom` is only used to keep that column from being auto-checked as an item in the wizard and to check it exists at validation; the tool computes no totaalscore of its own. Backward compatible: an older config whose first column is `kolom_naam` (no `meenemen`) is read with every row defaulting to meenemen=True.

The analyses group scores by **item name** (after `shorten_item`), so item names must be unique among the checked columns: two columns with the same name would silently merge into one item in which every student counts twice (doubled n, too-small p). `transformatie.dubbele_itemnamen` enforces this in `valideer_config`, the wizard's `bevestig_config`, and `transformeer_naar_lang` (raises). An empty item falls back to its `kolom_naam` (`item_naam`). Likewise a candidate may appear only once in the selection data: exact duplicate rows are counted once (validation warning), duplicates with different scores block (`_tegenstrijdige_kandidaten`). A config with no checked columns is a validation error.

## Demo data

Two datasets in `data/demo/`, deliberately different in shape so the demos don't look alike. Each mirrors a real (gitignored) source file:
- `demo_leiden_2026/` (Farmacie master, Universiteit Leiden, 140 candidates, 70 enrolled). Mirrors `dummy data selectie FAR Leiden 2025`: a master selection on sheet "2 Master beoordelingen" with a single header row (header_rij=1). Bachelordiploma assessment (gemiddeld cijfer + studietempo) plus two assessors (B1, B2) scoring NL documents, gesprek/schrijfopdracht and the selection interview. The `C_*_Sc_*` point columns add up to subtotals and `C_Sc_Totaal`. Because it is a master, the outcome is `diploma_behaald`, not year-2 doorstroom. 9 config items across instruments Bachelordiploma and Gesprek; the subtotals (`C_B1_B2_Sc_SubTotaal`, `C_A_Sc_SubTotaal`) are deliberately unchecked because they double-count their parts.
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
  bestanden.md           # explains the three input files, their formats and how the tool reads them, for end users
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

The Regressie tab runs a logistic regression predicting study success (doorstroom or diploma) from all selection items. This is the most fragile part of the tool because selection datasets are small and the items have wildly different scales.

### Problem 1: Different scales

Selection items range from 1-3 ordinal ratings to 0-100 percentages to raw schaalscores. In a raw logistic regression, items on larger scales dominate the model simply because a 1-unit change means something different for each scale.

**How we handle it:** All items are z-score standardized before entering the model (`(x - mean) / sd`). This means coefficients and odds ratios express the effect of a 1-SD increase, which is comparable across scales. The dashboard explains this to the user in the collapsible "Uitleg regressietabel" section.

**What it does NOT solve:** Z-scores make coefficients comparable, but they don't fix non-linear relationships or heavily skewed distributions. An item where 90% of candidates score the same value has almost no variance after standardization and contributes little to the model regardless.

### Problem 2: Too few observations for the number of predictors

The "events per variable" (EPV) rule says you need at least 5-10 events (students in the smallest outcome group) per predictor. A dataset with 30 enrolled students and 15 who dropped out can support at most 3 predictors at EPV=5. With 12 selection items, you get unstable estimates and inflated odds ratios.

**How we handle it:** `shared.bereken_gezamenlijk_model` (the single implementation shared by the Regressie tab, Wat valt op and the PDF report) computes `max_predictoren = max(2, min(n_positief, n_negatief) // 5)`. If there are more items than that, it runs univariate logistic regressions for each item, ranks them by p-value, and keeps only the top `max_predictoren`. Dropped items are listed above the regression table so the user knows what was excluded and why.

**What it does NOT solve:** Even with selection, the model may be overfitted. With small samples, a single outlier can flip a coefficient from significant to not. We don't bootstrap or cross-validate. The results should be read as "suggestive patterns", not definitive evidence. Because the items are pre-selected on their univariate p-value on the same data, the joint model's p-values are too optimistic; whenever `verwijderd_epv` is non-empty the Regressie tab, Wat valt op and the report say so (`shared.VOORSELECTIE_UITLEG`).

### Multiple testing

The per-item tests (verschiltoets per outcome, per demographic dimension, and the univariate regressions) test many items at once, so some come out below p = 0.05 by chance. `shared.bh_correctie` applies Benjamini-Hochberg (chosen over Holm, which is too strict for 50-150 students) per family of tests: one table = one family. Tables show the raw `p` and `p (gecorrigeerd)` (`shared.P_GECORRIGEERD`, numeric `_p_bh`); significance stars, the "Verschil" direction, `genereer_bevindingen`, `_tel_bevindingen` and the vervolgstappen all use the corrected p (`shared._p_kolom` falls back to `_p` for tables without `_p_bh`). The user-facing explanation is one constant, `shared.BH_UITLEG`, reused by the tabs and the report. The joint model is a single test and is not corrected.

### Policy framing (beleidsaudit, issues #46-#52)

- **Outcome is called retentie**, not studiesucces, in all user-facing text (`shared.RETENTIE_UITLEG`, the perspectives' `kanttekening`/`uitkomst_naam`). Year-2 enrollment is retention: repeaters count as doorgestroomd, switchers as not. Group labels (`GROEP_*`) are unchanged.
- **Null results are not evidence against the selection.** `beleidsvervolgstappen` never advises simplifying/cutting when nothing is significant. `genereer_bevindingen` returns `kanttekeningen`: the smallest detectable effect (`kleinste_aantoonbaar_effect`, 80% power, uncorrected, so a lower bound) and `BEREIKSBEPERKING_UITLEG` (range restriction: only admitted students have an outcome). Shown in Wat valt op, the Verschiltoets explanation and the report.
- **Background analysis is named for what it is**: "Scoreverschillen naar achtergrond (gestarte studenten)", not "eerlijkheid". Background comes from 1CHO, so rejected candidates are invisible; the text says so.
- **Retentie per scoregroep** (`retentie_per_scoregroep`): quartiles of started students per item (or one band per value when an item has ≤4 distinct values), share with the positive outcome. Verschiltoets tab and report section 3.
- **Small cells**: `MIN_CEL` (5). Use `cel_tekst` for counts and `afgeschermde_kruistabel` for crosstabs (suppresses the small cell, its row partner, and the Totaal row when exactly one row is suppressed). Suppressed groups are left out of charts and out of the demografie findings text.
- **Report provenance**: "Over dit rapport" table in the Inleiding (tool version from pyproject, date, opleiding, instelling, jaar, counts, MIN_CEL).
- **Privacy**: `docs/privacy-handleiding.md` (FG checklist), linked from README and the upload screen.

### Subtotals

A subtotal next to its parts double-counts and correlates with them by construction, so it tends to top the findings. `config_wizard.detecteer_somkolommen` flags a column whose name contains a (sub)totaal/som word (as a word part, see `_naam_delen`) or that equals the sum of a contiguous run of ≥2 other score columns. The wizard leaves those unchecked (with suggestions filled in) and explains why in `_somkolom_tip`.

### Problem 3: Multicollinearity

Selection instruments often overlap. A "competentietest reflecteren" and a "competentietest stressbestendigheid" may correlate at r=0.8. In a joint model, neither appears significant because each explains variance the other already covers.

**How we handle it:** `shared._verwijder_collineair` works in two steps. First, while the predictor matrix is rank-deficient, it removes a column from the most correlated pair. Then, while any item has a variance inflation factor above `_MAX_VIF` (10), it removes the item with the highest VIF. The VIF step is needed because derived columns (e.g. Radboud's "Gemiddelde kernvakken", the mean of three other items) keep the matrix just full-rank but blew the joint model up to odds ratios around e^60. Removed items are reported as "Items niet meegenomen (te veel overlap)".

**What it does NOT solve:** Correlations below the VIF threshold (r=0.7-0.8 between two items) still inflate standard errors. The correlation heatmap helps the user spot this.

### Problem 5: Separation

When an item (or the items together) splits the outcome groups (almost) perfectly, the maximum-likelihood estimate runs off to infinity. statsmodels does **not** raise; it warns and returns an absurd fit (OR ~1e16, p ~1). Unchecked, the strongest predictor showed as "ns" and was ranked last in the EPV pre-selection.

**How we handle it:** every Logit goes through `shared._fit_logit`, which flags `scheiding` (PerfectSeparationWarning, or fitted probabilities within `_SCHEIDING_EPS` of 0/1) and `niet_geconvergeerd`. Don't flag separation on coefficient size: large coefficients also come from collinearity. Univariate rows get `_probleem`, a NaN p (so they fall out of the BH family) and "scheidt volledig" in Sig. The joint model drops separating items up front (`verwijderd_scheiding`) and returns status `scheiding`/`fout` if the joint fit itself separates or doesn't converge. `SCHEIDING_UITLEG` is the shared user-facing text; "Wat valt op" reports separation as a strong signal and points to the Verschiltoets.

### Caching

`helpers.gezamenlijk_model_uit_stores` caches the joint model per (data-store, scores-store) pair, so the Regressie tab and "Wat valt op" (which recomputes on every visit) fit it once per dataset. It returns a deep copy. The selection Excel is also cached per upload string in `transformatie._lees_blad`/`_bladnamen`, because every validation trigger re-reads it; `parse_selectiedata` returns a copy.

### Problem 4: Missing data

Some items have missing values for a subset of candidates (optional modules, keuzevakken). Listwise deletion would throw away too many cases.

**How we handle it:** Items with >30% missing values are excluded entirely. For the remaining items, missing values are imputed with the column mean. This is conservative and slightly biases coefficients toward zero.

### Summary for developers

The regression output is useful for spotting patterns but should not be overinterpreted given typical sample sizes (50-150 enrolled students). The dashboard communicates this through the toelichting text and the pseudo R-squared. When changing the regression code, test with both demo datasets: demo_leiden (Farmacie master, 9 items, 70 enrolled, header_rij=1, diploma outcome) and demo_radboud (Psychologie bachelor, 7 items, 70 enrolled, header_rij=3, doorstroom outcome). They differ in shape on purpose, so passing both exercises both the master/diploma and bachelor/doorstroom paths.

## Known gotchas

- **No .claudeignore**: the `data/` and `.venv/` directories are large. Don't glob or grep into them.
- **The data stores hold JSON strings** in `dcc.Store` (data-store, scores-store). Tab callbacks deserialize with `helpers.df_from_store()` / `scores_df_from_store()`, which pin `studentnummer` to `str` (plain `read_json` turns `"00123"` into `123`). Don't call `pd.read_json` on a store directly.
- **The 1CHO upload route** (`bestandsopslag.py`) rejects cross-origin POSTs (Origin check) and bodies over `MAX_UPLOAD_BYTES`. Uploads contain personal data: "Nieuw bestand laden" deletes the file (`verwijder_upload`) and clears the `cho-bestand` store, and files older than 24h are removed at startup.
- **Table `filter_query` strings with data values** must go through `helpers.query_tekst()`, which escapes quotes and backslashes. Group labels come from the data (vooropleiding descriptions can contain quotes).
- **The config wizard** (`config_wizard.py`) registers its own callbacks via `registreer_callbacks(app)`, wired in app.py. It shares the upload components with uploads.py.
- **fpdf2 SVG support** is limited. The NKO logo uses a PNG version (`assets/nko-logo.png`) for PDF rendering; the SVG (`assets/nko-logo.svg`) is only for the web dashboard.
- **statsmodels import** is done lazily inside the regression code (`shared.bereken_gezamenlijk_model()`, `shared.bereken_univariaat()`) because it is slow to import and only needed for regression.
- **No Configuratie tab**: it was removed at the user's request, along with its `config-store`/`raw-selectie-store`/`raw-cho-store` stores. Don't re-add those stores unless that feature comes back.

## Multi-session coordination

Multiple Claude Code sessions work on this project in parallel. Rules:

- **config_wizard.py** is self-contained. Changes there don't conflict with other work.
- **app.py** holds only layout composition and wiring. Tab work is isolated per `tabs/*.py` module, so two sessions on different tabs don't conflict. Shared helpers live in helpers.py; touching those is the higher-conflict area.
- **rapport.py** and **shared.py** are owned by the rapport/dashboard session.
- **scripts/eenmalig/maak_presentatie.py** generates the PowerPoint. Update it when features change.
- Always check `git status` before committing. Another session may have staged or committed while you were working.
- Never commit data files, PDFs, or docx. The gitignore handles this, but double-check.

## Known issues (not yet fixed)

These were identified during the audit but left unfixed. Pick them up when relevant.

### Code quality
- **Large callbacks**: `update_regressie_tab` and `update_verschiltoets_tab` do a lot of work inline. Splitting data prep from layout would improve readability.

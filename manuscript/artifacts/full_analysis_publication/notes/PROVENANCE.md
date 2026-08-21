# PROVENANCE

All figures and tables in this artifact set are derived exclusively from the
already-audited outputs of the confirmatory full-cohort run at:

    results/bci-calibration-full-v1-3fb8efe7e617b0c1

Generator script: `manuscript/artifacts/full_analysis_publication/build_artifacts.py`
(deterministic; reads the CSVs/JSONs below and writes figures/tables/source
data; performs no new inferential analysis, no re-fitting, and no
re-scoring).

## Input files used

- `curve_summary.csv` — participant-bootstrap calibration curves (Figures 2, Supplement Zhou2016 figure)
- `aucc_subject.csv` — participant-level fixed-horizon AUCC (curve-completeness check only in this build)
- `pairwise_tests.csv` — confirmatory + supportive paired contrasts (Figure 3, Tables 2 and Supplement)
- `mixed_effects_coefficients.csv` — mixed-effects model terms (Table 3)
- `mixed_effects_diagnostics.json` — model formula, convergence, warnings (Table 3 caption/footnote)
- `summary_subject.csv` — repeat-averaged participant-level outcomes (Figure 4)
- `participant_flow.csv` — attempted/succeeded/failed counts per dataset (Table 1, cross-checked by assertion)
- `result_audit.json` — integrity audit status and counts (Supplement audit note)
- `aggregation_manifest.json` — aggregation checksums (Supplement audit note)
- `run_manifest.json` — experiment/preprocessing fingerprints (Supplement audit note)

`metrics.csv` and `predictions.csv.gz` were **not** re-read or recomputed by
this script; they are the inputs the audit already verified metrics.csv/
aggregated tables against, and this build trusts the audited aggregates.

## Filtering / subsetting logic (no new statistics)

- **Figure 2**: `curve_summary.csv` filtered to `dataset in {Lee2019_MI,
  BNCI2014_001}`, `regime in {subject, source_plus_target}`,
  `metric == "roc_auc"`, laid out as a 2 (dataset) × 3 (method) grid, with
  the two regimes overlaid within each panel on the shared budget axis.
  Zhou2016 excluded per the pre-registered treatment of that dataset as
  descriptive/supportive only.
- **Figure 3**: `pairwise_tests.csv` filtered to
  `family in {H2_regime_low_budget_confirmatory,
  H2_regime_low_budget_dataset_supportive}`, `budget_per_class in {5, 10}`,
  `scope_dataset in {ALL, Lee2019_MI, BNCI2014_001}` (Zhou2016 excluded).
  p-value annotations are drawn only for `scope_dataset == "ALL"` rows
  (already-computed `p_holm` values; no new test or threshold).
- **Figure 4**: `summary_subject.csv` filtered to `method == "riemann_lr"`,
  `dataset in {Lee2019_MI, BNCI2014_001}`, `regime in {subject,
  source_plus_target}`, pivoted participant × budget.
- **Table 1**: static protocol facts (nominal N, sessions, channels, task)
  from the dataset registry / README; final validated N cross-checked by
  assertion against `participant_flow.csv`; exclusion detail from
  `docs/DECISIONS.md`.
- **Table 2**: `pairwise_tests.csv` filtered to
  `family == "H2_regime_low_budget_confirmatory"` (all rows) plus
  `family == "H3_method_aucc_confirmatory" and regime == "subject"`.
- **Table 3**: `mixed_effects_coefficients.csv` with the three random-effect
  variance-component rows (`Group Var`, `Group x log2_budget Cov`,
  `log2_budget Var`) moved to a separate supplement CSV
  (`Table3_mixed_effects_variance_components_supplement.csv`); the remaining
  14 fixed-effect and interaction terms are split into a compact main-text
  table (`Table3_mixed_effects_summary`, the 8 terms in `MAIN_TABLE_TERMS`:
  intercept, regime, log2(budget+1), their interaction, the two method main
  effects, and the two dataset fixed effects) and a complete supplement
  table with all 14 terms (`Table3_mixed_effects_full_supplement`). Row
  selection only; no coefficient, standard error, or p-value is altered
  between the two tables.
- **Supplement figure**: same construction as Figure 2, `dataset ==
  "Zhou2016"` only.
- **Supplement table**: `pairwise_tests.csv` filtered to
  `inference_role == "supportive"` (all dataset-specific H2 and H3 rows,
  including Zhou2016).

## Derived-for-display-only calculations

- `x = log2(budget_per_class + 1)` — a monotonic axis transform for legible
  spacing of 0/5/10/20/40; the underlying values plotted are the audited
  `mean`/`ci_lower`/`ci_upper` from `curve_summary.csv`, unchanged.
- Figure 4 participant row order: each dataset's participants are sorted by
  their own mean `source_plus_target` ROC-AUC across budgets (from
  `summary_subject.csv`), and that order is reused for the `subject`-regime
  panel of the same dataset. This is a display ordering only; it does not
  alter, select, or re-weight any value.
- Significance markers (`*`) in tables mark `p_holm < 0.05` (Table 3:
  uncorrected model `p < 0.05`, a single fitted model, not a
  multiple-comparison family) using the already-computed p-values; no new
  threshold, test, or correction is introduced. In Figure 3, p-value text
  annotations are drawn only next to the pooled confirmatory diamonds
  (`scope_dataset == "ALL"`); dataset-specific supportive points still show
  their confidence intervals but are not individually p-annotated, to keep
  the confirmatory/supportive distinction visually unambiguous. Figure 3's
  annotations read as plain text (e.g. "Holm p < 0.001", "Holm p = 0.016")
  with no significance star, since the adjusted p-value itself is already
  the displayed signal; this is a label-formatting change only, using the
  same `p_holm` values as before.
- Figure 2's title and caption were revised to state the pattern precisely
  rather than as a general "convergence" claim: Lee2019_MI shows a
  low-budget pooled advantage that converges/crosses over by budget 40 for
  all three decoders; BNCI2014_001 is method-dependent, with log-variance +
  LDA and CSP + LDA following the same pattern as Lee2019_MI but Riemannian
  TS + LR already favoring subject-only at the lowest calibrated budget
  shown (5 trials/class: 0.731 vs. 0.678, from `curve_summary.csv`). No
  plotted curve, CI, or panel changed; only the title text and caption
  wording changed.

## LaTeX layout (tables only; no data change)

Fixed real width/rendering problems found by compiling the previous version
of these tables with `pdflatex`: Table 1 (confirmatory-role column clipped,
~420pt overfull), Table 2 (~100pt overfull, rightmost effect-size column
clipped), the dataset-specific supplement table (~82pt overfull), and
Table 3's footnote rendering beside rather than below the table rows.

- **Table 1**: rebuilt with `tabularx`, `Confirmatory role` set as the `X`
  (wrapping) column; the `Task` column text shortened to "Left/right motor
  imagery" (was "Left- vs. right-hand motor imagery"). No row, count, or
  scientific content removed.
- **Table 2**: rebuilt with `tabularx`; the previously-combined "Condition"
  text column is now two explicit columns (`Method`, `Budget / regime`);
  the unadjusted raw `p` column is omitted from this rendering only (it
  remains a column in `Table2_confirmatory_contrasts.csv`, unchanged);
  `p_holm` and `rank_biserial` are both retained. Wrapped in
  `threeparttable` so the footnote renders below the table.
- **Supplement dataset-specific contrasts table**: rebuilt with
  `tabularx`, `Condition` set as the `X` column; wrapped in
  `threeparttable`. No row or value removed.
- **Table 3 (main and full supplement)**: both wrapped in `threeparttable`
  via the shared `_render_mixed_effects_table()` helper, replacing the
  previous vspace-plus-inline-footnotesize pattern that rendered beside the
  table. No coefficient, standard error, or p-value changed.

No `pdflatex` (or other LaTeX compiler) was available in the environment
that produced this build; see `notes/Supplement_Audit_Provenance.md` (or
the task's final report) for the explicit compiler-availability statement.
The fixes above follow the specific overfull/clipping measurements reported
from an independent `pdflatex` compilation and standard `tabularx`/
`threeparttable` usage, but were not compiled by this script itself.

## Consistency checks run by the generator

- Asserts `participant_flow.csv` attempted counts equal the expected
  structurally validated cohort (Lee2019_MI 54, BNCI2014_001 9, Zhou2016 2)
  before building Table 1.
- Asserts `result_audit.json["status"] == "ok"` before building anything.
- Asserts every declared `MAIN_TABLE_TERMS` entry actually exists in
  `mixed_effects_coefficients.csv` before building Table 3.
- Scans every generated `.tex` file for the literal string
  `textbackslash{}times` and fails the build if found. This string is what
  `tex_escape()` previously produced when a pre-written `$\times$` LaTeX
  command was passed back through it (the backslash was escaped a second
  time, breaking compilation). The fix: interaction-term labels now store a
  plain Unicode "×" character, and `tex_escape()` is the single place that
  converts "×" to `$\times$`, so no string is ever escaped twice.

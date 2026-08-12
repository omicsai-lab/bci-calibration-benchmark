# Journal and publication strategy

## Paper type

This is a reproducible multi-dataset benchmark/methodological evaluation, not a new hardware report and not primarily a novel neural architecture paper.

## Recommended sequence

### 1. Biomedical Signal Processing and Control

Best initial fit for a rapid but substantial paper. Its scope explicitly includes biomedical signal processing such as EEG, and it regularly publishes BCI decoding and transfer-learning studies. The manuscript should emphasize signal-processing rigor, cross-session evaluation, calibration burden, and reproducibility rather than broad neuroscience claims.

### 2. Journal of Neural Engineering

A stronger but more demanding option if the full results show a clear engineering conclusion, robust cross-dataset consistency, and a convincing practical calibration implication. A purely descriptive benchmark may be insufficient unless it changes how BCI evaluation or deployment should be designed.

### 3. Scientific Reports

A plausible broad-scope option if the study is framed as an empirical cross-session result with transparent methods, adequate cohort size, and complete reproducibility. Avoid presenting a minor classifier comparison as the contribution.

### 4. Brain-Computer Interfaces

A natural specialist destination if broader journals reject the paper or if the strongest contribution is evaluation practice and user calibration rather than signal-processing novelty.

## Submission decision rule

- **Compelling, consistent result with operational threshold/heterogeneity insight:** consider *Journal of Neural Engineering* first.
- **Solid benchmark with useful but not field-changing differences:** submit to *Biomedical Signal Processing and Control* first.
- **Strong empirical story, broad reproducibility emphasis:** *Scientific Reports*.
- **Technically sound specialist paper with narrower reach:** *Brain-Computer Interfaces*.

## Required manuscript positioning

The introduction must distinguish the study from:

- architecture-centered MI classification papers;
- within-session MOABB rankings;
- calibration-free/domain-adaptation method papers;
- recent subject-heterogeneity pipeline benchmarks;
- longitudinal online fine-tuning studies.

The contribution is the combination of:

1. complete latest-session holdout;
2. identical fixed test set across methods and calibration budgets;
3. nested labeled target calibration budgets;
4. population, target-only, and pooled retraining regimes;
5. participant-level inference and proper uncertainty;
6. public, auditable trial assignments and predictions;
7. explicit cue-related and dataset-heterogeneity limitations.

## Desk-reject risks

- appearing to be only “three standard classifiers on three datasets”;
- claiming novelty for pooled source-plus-target training;
- treating repeated calibration samples or trials as independent N;
- reporting only grand mean accuracy;
- ignoring recent 2025–2026 benchmarks/adaptation literature;
- no biological sanity check or cue-confound discussion;
- unvalidated public adapter assumptions;
- excessive claims about clinical BCI deployment.

## Minimum submission package

- manuscript and supplement;
- frozen configs;
- participant flow and dataset table;
- full participant-level aggregate results;
- pairwise and mixed-model outputs;
- result audit and manifests;
- figure-source CSVs;
- tagged repository release and DOI;
- exact environment freeze;
- original dataset and software citations.

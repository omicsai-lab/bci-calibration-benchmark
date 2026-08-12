# Dataset notes, provenance, and licensing

This repository does not redistribute source EEG. MOABB retrieves data from original hosts, and every user remains responsible for the source license, citation, storage, and access terms.

## Confirmatory set

### `Lee2019_MI`

- Original resource: OpenBMI motor-imagery dataset.
- Participants: 54.
- Sessions: 2 on different days.
- EEG: 62 channels, originally sampled at 1,000 Hz.
- Task: left-hand versus right-hand motor imagery.
- Confirmatory trials: labeled offline training phase only, 50 trials/class/session.
- Adapter construction: `Lee2019_MI(train_run=True, test_run=False, resting_state=False)`.
- Original paper: Lee et al., *GigaScience* (2019), DOI `10.1093/gigascience/giz002`.
- MOABB dataset page: <https://moabb.neurotechx.com/docs/generated/moabb.datasets.Lee2019_MI.html>
- MOABB page reports a GPL-3.0 dataset license; verify the original distribution terms before redistribution or derivative release.

The online-feedback/test phase is excluded because it is unlabeled in the adapter and would not support the same supervised calibration estimand.

### `BNCI2014_001`

- Common name: BCI Competition IV Dataset 2a.
- Participants: 9.
- Sessions: 2, each containing 6 runs.
- EEG: 22 channels, 250 Hz; three EOG channels exist in the source but are not included as EEG features.
- Native classes: left hand, right hand, feet, tongue.
- Confirmatory task: left versus right only, yielding 72 trials/class/session.
- Feedback: none.
- Reference paper: Tangermann et al., *Frontiers in Neuroscience* (2012), DOI `10.3389/fnins.2012.00055`.
- MOABB dataset page: <https://moabb.neurotechx.com/docs/generated/moabb.datasets.BNCI2014_001.html>
- MOABB reports CC BY-ND 4.0; source data are not redistributed here.

### `Zhou2016`

- Participants: 4 experienced BCI users.
- Sessions: 3, separated by days to months.
- Runs: 2/session.
- EEG: 14 channels, 250 Hz.
- Native classes: left hand, right hand, feet.
- Confirmatory task: left versus right only, yielding 50 trials/class/session.
- Feedback: none.
- Original paper: Zhou et al., *PLOS ONE* (2016), DOI `10.1371/journal.pone.0162657`.
- Data record DOI: `10.6084/m9.figshare.2061654`.
- MOABB dataset page: <https://moabb.neurotechx.com/docs/generated/moabb.datasets.Zhou2016.html>

Zhou2016 is small and cannot carry a pooled conclusion by itself. Its role is protocol replication across three sessions and a different acquisition setup.

## Datasets examined but not included in v0.1

### `Cho2017`

The current MOABB representation does not expose multiple sessions/runs suitable for the strict latest-session confirmatory split. It remains valuable for within-session or cross-subject studies but does not answer this protocol's prospective cross-session question without trial-level fallback.

### `PhysionetMI`

The current MOABB representation similarly does not provide the required multi-session prospective structure for this analysis. It is not excluded because of data quality or expected performance.

### `BNCI2014_004`

The dataset has five sessions, but the latest three include continuous smiley feedback whereas the first two do not. A fixed latest-session holdout would conflate calibration with a protocol/feedback change.

### `Yang2025`

This recent multi-day dataset is highly relevant: the two-class subset contains 51 participants and 3 sessions. It is not in v0.1 because the source distribution is a large single archive and the adapter has not yet passed this repository's local structural and compute pilot. It is a strong candidate for a later external-validation release, not a post hoc rescue dataset.

## Common task and non-equivalence

The three confirmatory datasets share left/right cue-based motor imagery, but they are not interchangeable. They differ in montage, reference, sampling, cue timing, user experience, session spacing, and native task structure. The pipeline harmonizes a narrow signal-processing task; it does not erase biological or experimental heterogeneity.

Consequently:

- models are trained and evaluated within dataset;
- source participants come from the target dataset only;
- dataset is retained in every report and model;
- pooled estimates are accompanied by dataset-specific estimates;
- no epoch-level pooling across datasets is performed.

## Required citations

A publication using this repository must cite:

1. the original paper/data record for every included dataset;
2. MOABB and the exact MOABB software version;
3. MNE-Python and the methods used where appropriate;
4. this repository release/DOI once archived.

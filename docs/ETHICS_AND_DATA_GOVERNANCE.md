# Ethics and data governance

## Secondary analysis

This project performs secondary analysis of previously collected public EEG datasets. It does not recruit participants, deliver stimulation, control a device, or provide clinical care.

The original investigators' consent and ethics statements govern source collection. Users must review the original publications and repository terms before use. Institutional review requirements for secondary public-data analysis vary and remain the responsibility of the research team.

## Data minimization

Only public dataset participant identifiers are retained. The repository must not introduce names, contact details, private clinical information, or attempts to re-identify participants.

Raw EEG is excluded from version control. Processed arrays and predictions can still be sensitive biometric data and should not be publicly redistributed without reviewing source terms and institutional policy.

## EEG privacy

EEG may contain information beyond the intended motor-imagery label, including identity-related or health-related signal. Public availability does not make unrestricted re-identification or unrelated phenotyping ethically neutral. This benchmark uses EEG only for the declared left/right motor-imagery task.

## Claims boundary

The repository does not support claims of:

- clinical efficacy;
- safety of a BCI device;
- online control performance;
- rehabilitation benefit;
- diagnostic or prognostic validity;
- pure motor-intent decoding free of visual-cue information.

## Bias and generalizability

The selected datasets primarily contain healthy research volunteers and differ in experience, geography, hardware, and protocol. Performance cannot be generalized directly to patients, children, older adults, home use, dry electrodes, or online closed-loop BCI operation.

Participant-level heterogeneity must be reported. Low-performing participants are not discarded or labeled deficient.

## Responsible release

A public release should include code, configs, manifests, aggregate tables, and figure-source data where source terms allow. It should exclude raw EEG, credentials, local paths, private notes, and unreviewed participant-level metadata not necessary for reproducibility.

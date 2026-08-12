# Data directory

Raw and processed EEG are excluded from version control.

Default layout after preparation:

```text
data/
├── moabb-cache/                         # MOABB/MNE downloads; never committed
└── processed/
    └── <preprocessing-fingerprint>/
        └── <dataset>/
            ├── dataset_manifest.json
            └── subject-<ID>/
                ├── X.npy
                ├── y.npy
                ├── metadata.csv.gz
                └── manifest.json
```

Each subject manifest records identity, shape, dtype, sampling frequency, channel order, class/group counts, preprocessing, package versions, and SHA-256 checksums. Each dataset manifest hashes the subject manifests.

Processed EEG and predictions may still be biometric data. Do not redistribute them merely because the source dataset is public. Review the original license, consent language, institutional policy, and data-host terms.

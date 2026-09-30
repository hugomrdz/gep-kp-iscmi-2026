# Benchmark attribution and frozen inputs

The MIT license covers the original code and documentation in this repository. It does not grant additional rights to third-party benchmark data. The archived benchmark files are kept unchanged, with their original source documentation. No separate dataset license was present in the copied materials; consult each original source for its terms.

## Jooken hard 0–1 knapsack instances

Source repository: <https://github.com/JorikJooken/knapsackProblemInstances>

Source revision recorded inside the frozen ZIP: `df45dfade087aa3aa4ec8665e157efe362d20df7`.

Archive: `data/knapsack.zip` (21,305,404 bytes), SHA-256:

```text
68ef9b6be17fbc37f303a250aa79cacfcbe7167d5f0b83f8f96c60d666f0fb26
```

The archive has 3,240 instances: 2,977 with supplied certified optima and 263 unresolved. Its original internal directory is `knapsackProblemInstances-master/`. A new download of the current branch, or even a differently wrapped commit ZIP, need not have the original archive hash. Restore the exact frozen file through `scripts/artifacts.py` to satisfy the protocol's byte-level check.

Please cite Jorik Jooken, Pieter Leyman, and Patrick De Causmaecker, “A new class of hard problem instances for the 0–1 knapsack problem,” European Journal of Operational Research 301(3), 841–854 (2022), as requested by the source archive.

## Pisinger transfer instances

Source: <https://hjemmesider.diku.dk/~pisinger/codes.html>

The small-coefficient, large-coefficient, and hard-instance archives contain 31,800 retained cases. Each supplied 0/1 solution was checked against its stated optimum and capacity. Direct source links, retrieval record, byte sizes, and SHA-256 fingerprints are preserved in [the original source audit](../protocol/pisinger_sources.md).

The local release asset contains the exact four archives used by the paper. The full member and bundle checksums are in [artifacts/manifest.json](../artifacts/manifest.json).

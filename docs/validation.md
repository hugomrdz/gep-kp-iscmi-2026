# Publication-package validation

Validated locally on 2026-09-30 using CPython 3.14.7 and the installed pinned Python dependencies. The historical experiment environment remains unchanged in `results/environment_v2.json` (CPython 3.14.3).

- **Clean Git-only checkout:** 35 tests passed; publication provenance and all three paper-figure builds passed without benchmark or raw-evaluation files.
- **Source provenance:** all 50 original locked artifacts verified; four packaging adaptations recorded; original protocol-lock bytes and archived original source bytes retained.
- **Completed experiment:** 1,138 valid atomic run directories, 675 final models, 3,900 checkpoints, 31,800 transfer certificates, and 12 hashed evaluation files verified.
- **Statistical reproduction:** reran the full original analysis from raw evaluations. All 20 checked compact result files were byte-identical to the original snapshot. `provenance/analysis_reference.json` records the reference fingerprints.
- **Paper figures:** all three regenerated PDFs matched the corrected reference figures pixel-for-pixel at 180 DPI and retained identical extracted text. Figure 1 includes the final tight crop.
- **Notebook:** rebuilt and executed all 11 code cells successfully.
- **Training smoke checks:** four terminal arms passed random-gene structure, batch/scalar/independent decoding, exact-budget, and seeded-repeat checks; named fixed rules matched their expression implementations.
- **R tuning interface:** the recorded irace 4.4.3.9000 scenario check and its two target-runner trials passed. The full tuning race was not repeated. Original tuning records were restored after the check.
- **Release assets:** both deterministic bundles and all 16 member files passed SHA-256 verification. An empty independent tree successfully restored both bundles offline. Permanent tests cover corruption, path traversal, archive links, and destination symlinks.
- **Fresh final-replication workspace:** the helper created a separate workspace that passes the original scientific lock checks and has no completed final/oracle runs, trained models, or evaluation/analysis outputs.

The full multi-hour 675-model training/evaluation experiment was not repeated during packaging. The supplied code, frozen inputs, seeds, and separate-workspace command support that reproduction. No GitHub repository or release was created or uploaded during this preparation.

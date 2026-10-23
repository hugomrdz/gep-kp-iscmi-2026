# Publication-package validation

## Public-use review, 2026-10-23

Checked the revised paper and comparison at commit `b429522`, using a newly installed Python 3.14.7 environment with the pinned requirements, R 4.6.1, class 7.3-23, and Tectonic 0.17.0. Dependency checks reported no conflicts.

- **Tests:** all 45 tests passed in the working repository and in a separate copy containing only Git-tracked files. The separate copy also passed source verification and rebuilt all three paper figures without benchmark downloads.
- **Original experiment:** all 50 locked source and input records passed verification. Checks also passed for 1,138 run directories, 675 final models, 3,900 checkpoints, 31,800 transfer certificates, 12 hashed evaluation files, and the saved notebook. All 20 reference result files retain their original fingerprints.
- **Release artifacts:** both cached bundles and all 16 restored member files matched the published checksums. Both public download URLs responded successfully without authentication. The repository and `artifacts-v1` release are public, and the [GitHub test run for this commit](https://github.com/hugomrdz/gep-kp-iscmi-2026/actions/runs/39743499914) passed.
- **Additional comparison:** reran all nine methods on the 1,594 test instances and verified all 14,346 outcomes. The 10 scientific output files, including predictions, outcomes, summaries, bootstrap samples, intervals, and the original-result replay check, were byte-identical to the published comparison. Timing and runtime records were excluded from that equality check.
- **Paper:** rebuilt the submission folder independently. All five rendered pages matched the saved PDF pixel for pixel. Visual inspection found no clipping or overlapping content, and all 24 font entries were embedded. The README's reported means agree with the saved CSV files, and all six Table IV rows agree with the manuscript.
- **Documentation:** added a short starting point, explained the original FULL-versus-BASE finding, linked the reusable CSV files, clarified the comparison's environment requirements, and moved data restoration before verification in the comparison guide. All local Markdown file links resolve.
- **Repository contents:** Git reported no object corruption. A scan of tracked text and compressed tables found no matches for common credential patterns. The paper and citation metadata list Hugo Abel Moreno-Rodriguez and José Carlos Ortiz-Bayliss.

The original tuning, full training, and full statistical reanalysis were not repeated in this review. Their saved artifacts and fingerprints were verified; the additional comparison was recomputed. The documentation changes leave the scientific code, protocol locks, recorded results, and paper files unchanged.

## Original packaging review, 2026-09-30

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

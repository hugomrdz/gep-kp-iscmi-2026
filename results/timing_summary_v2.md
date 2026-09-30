# ISCMI 2026 V2 runtime notes

These timings are descriptive reproducibility information. They are not a
statistical outcome and are not part of any solution-quality comparison.

## Hardware and concurrency

- Study laptop: MacBook Pro `Mac14,9` with Apple M2 Pro.
- CPU: 10 cores (6 performance and 4 efficiency cores).
- Memory: 16 GB.
- Operating system: macOS 26.5.2 (`25F84`), Darwin 25.5.0.
- Main final training used four parallel terminal-arm workers. Numerical-library
  threads were limited to one per worker through `OMP_NUM_THREADS=1`,
  `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`,
  `VECLIB_MAXIMUM_THREADS=1`, and `NUMBA_NUM_THREADS=1`.
- The 75 historical AHDAS continuity-control runs followed serially.

These machine-specific timings should not be presented as universal performance
measurements.

## Reconstructed completed stages

The irace tuning stage took approximately five hours of wall-clock computation
on the study laptop. This is an **approximate reconstructed value**; irace was not
rerun merely to obtain cleaner timing data.

Final training completed all 675 frozen models with exit status 0 and without an
interruption or resume. Its approximate launch-to-completion wall time was
`66,289.168` seconds (`18.414` hours), from approximately
`2026-08-29T11:59:36.161637+00:00` to
`2026-08-30T06:24:25.330023+00:00`. The launch timestamp is reconstructed from
the first atomic completion in each of the four workers; the finish timestamp is
the merged-model artifact time.

The exact sum of the stored `elapsed_seconds` fields across all 675 runs is
`224,563.80308862100351` seconds (`62.379` hours). This is **total worker-time**,
not wall-clock duration: four workers ran concurrently during the main GEP and
matched-random phase, followed by the serial AHDAS control.

## Completed-stage timings

All timestamps below are UTC. `Interrupted` means the running command received an
interruption; `resumed` means a later attempt continued the stage.

| Stage | Start UTC | Finish UTC | Wall seconds | Exit | Interrupted | Resumed |
|---|---|---|---:|---:|---|---|
| Final training (reconstructed launch) | 2026-08-29T11:59:36.161637+00:00 | 2026-08-30T06:24:25.330023+00:00 | 66,289.168 | 0 | no | no |
| Locked evaluation | 2026-08-30T09:19:33.619696+00:00 | 2026-08-30T10:30:31.495058+00:00 | 4,257.900 | 0 | no | no |
| Unresolved-oracle solving | 2026-08-30T10:31:32.649792+00:00 | 2026-08-30T11:37:36.630590+00:00 | 3,963.998 | 0 | no | no |
| Statistical analysis and figures | 2026-08-30T11:38:05.758465+00:00 | 2026-08-30T11:40:29.960729+00:00 | 144.202 | 0 | no | no |
| Notebook attempt 1 | 2026-08-30T11:40:41.366591+00:00 | 2026-08-30T11:40:42.140733+00:00 | 0.774 | 2 | no | no |
| Notebook resumed attempt | 2026-08-30T11:57:01.370071+00:00 | 2026-08-30T11:57:04.978831+00:00 | 3.609 | 0 | no | yes |
| Final verification | 2026-08-30T11:57:25.196079+00:00 | 2026-08-30T11:57:28.863039+00:00 | 3.667 | 0 | no | no |

Notebook attempt 1 ended before cell execution because the managed sandbox denied
the local Jupyter kernel socket. The same command was resumed after local-socket
approval and completed successfully. The approximately 16-minute approval gap is
not counted as computation. No locked source or protocol file was changed.

The unresolved-oracle stage attempted all 263 cases. All returned solver status 1,
so zero new exact optima were certified. Its exact summed per-case solver time was
`15,782.718984298408031` seconds (`4.384` hours) of worker-time; the four workers
ran in parallel, giving `3,963.998` seconds of wall time. Solver bounds remain
available for bounded-gap reporting, but no approximate result was relabeled as an
exact oracle.

## Evaluation boundaries and throughput

The locked evaluation command completed `41,503,185` model/method-instance
evaluations in `4,257.900` seconds, or about `9,747.34` evaluations per second.

| Evaluation component | Observable start UTC | Observable finish UTC | Wall seconds | Evaluations | Evaluations/s |
|---|---|---|---:|---:|---:|
| Original-order Jooken | 2026-08-30T09:19:33.619696+00:00 | 2026-08-30T09:23:35.036730+00:00 | 241.417 | 7,251,585 | 30,037.59 |
| Ten row permutations | 2026-08-30T09:23:35.036730+00:00 | 2026-08-30T09:33:27.253918+00:00 | 592.217 | 12,627,600 | 21,322.58 |
| Pisinger transfer | 2026-08-30T09:33:29.038798+00:00 | 2026-08-30T10:30:30.825480+00:00 | 3,421.787 | 21,624,000 | 6,319.51 |

The original-Jooken finish and row-permutation boundaries are atomic file
timestamps. The Pisinger start is the captured first-batch marker and its finish is
the atomic transfer-file timestamp. About 2.48 seconds of aggregate process,
transition, manifest, and shutdown overhead is therefore not assigned to a
component. Pisinger throughput is lower because instance sizes vary up to 10,000
items; these rates are descriptive machine-specific measurements, not algorithmic
quality metrics.

## Verification outcome

Final verification passed: the signed protocol hashes matched, all 35 V1 history
files were unchanged, 1,138 atomic run directories validated, all 31,800 transfer
certificates were present, 675 final models and 3,900 checkpoints were complete,
12 evaluation files matched their hashes, publication analysis and figures were
present, and all 11 notebook code cells were executed with dollar-delimited math.

# Reproducing the ISCMI 2026 experiment

## Frozen state

The distributed experiment is already complete. `protocol/protocol_lock.json` records the original pre-evaluation approval, and `provenance/publication_manifest.json` verifies its original inputs plus declared packaging adaptations. Do not regenerate this manifest to accept scientific changes. `make verify-provenance` detects missing, modified, and extra locked sources without accessing the old development workspace.

The standalone source has the same evolutionary search, decoding, instance parsing, bootstrap, and statistical computations as `iscmi2026_v2`. The paper figure builder has the later requested presentation corrections. The notebook and historical records may display the original machine's paths or timings; those are provenance, not runtime dependencies.

## Setup and validation

Use Python 3.14 with the versions pinned in `requirements.txt`.

The full test suite also includes the additional kNN comparison, so install R with the `class` package before running `make test`. The [comparison instructions](../revision_comparison/README.md) document its recorded environment and separate reproduction commands.

```bash
make setup
make test
make fetch
make verify
make smoke
```

`make smoke` uses a small training-only sample to compare batch, scalar, and independent decoders and to check seeded repeatability. `make verify` checks the data hashes, 31,800 transfer certificates, all atomic run hashes, 675 final models, 3,900 checkpoints, all 12 evaluation hashes, summary outputs, and executed notebook.

All Make targets run from the repository root. For non-notebook commands, `PYTHON=/path/to/python` selects an existing environment; the notebook retains its original `.venv` interpreter check. `WORKERS=1` reduces training and oracle parallelism. Numerical library thread counts are fixed to one by the Makefile.

## Reanalysis and paper figures

```bash
make reproduce
make notebook
make verify
python3 scripts/check_reference_results.py
```

The analysis reads 7,251,585 original Jooken evaluation rows, 12,627,600 row-permutation rows, and 21,624,000 Pisinger evaluation rows. It uses 10,000 crossed seed/group bootstrap replicates. The analysis input checker requires every evaluation file before the statistical code runs. `make paper-figures` alone works from compact tables without downloading the large artifacts.

The reference checker compares 20 compact result files with their exact original SHA-256 fingerprints. The packaging validation reproduced all 20 byte-for-byte. If another numerical platform gives a byte mismatch, inspect the numerical differences rather than replacing the reference fingerprints.

The corrected figure mapping is:

| PDF | Source figure | Presentation |
|---|---|---|
| `fig01.pdf` | study flow | Footer removed; tight vertical margins |
| `fig02.pdf` | headline effects | Titles replaced with bottom (a)/(b); fonts increased 20% |
| `fig03.pdf` | generalization, budget, robustness | Titles replaced with bottom (a)/(b)/(c) |

## Recompute the final experiment

First fetch the benchmark data in the published repository. Then:

```bash
.venv/bin/python scripts/new_replication.py ../iscmi-replication
cd ../iscmi-replication
make setup
make confirmatory WORKERS=4
make analyze
make notebook
make paper-figures
make verify
```

The helper refuses an existing destination and copies the fixed development inputs, selected configuration, frozen seeds, code, and benchmark archives. It omits final trained models, final/oracle run directories, checkpoints, and evaluation/analysis outputs. Consequently `train-final` must recompute them. It never deletes results from the source repository. The locked development artifacts are unchanged, and the original scientific protocol remains the basis of the replication.

Training and evaluation can take many hours. Atomic run directories permit interrupted training to resume. Evaluation has its own saved-file resume behavior. The unresolved exact-solver stage has time-limited solves; solver timing and unresolved certification outcomes can depend on the machine. Floating-point fits and execution times can also differ across platforms; the fixed seeds, budgets, and data are preserved.

## Development and tuning evidence

The original 2,000-trial irace race, five-candidate/four-arm/ten-seed survivor comparison, selected configuration, and R recovery files are included. No tuning is necessary for the frozen final reproduction above.

For inspecting the R scenario, install the recorded R/irace environment and run:

```bash
IRACE_CHECK_ONLY=1 Rscript tuning/run_irace.R
```

This check executes two target-runner trials and writes their records under `tuning/work/target-results`; it does not launch the full race. Run it in a disposable copy to retain the published tuning records untouched. The runner normally uses `.venv/bin/python`; `ISCMI_PYTHON=/path/to/python` overrides it.

A new tuning experiment belongs in a separate workspace. The retained `run_irace.R`, `finalize_irace.R`, and survivor implementation permit such research, but altered tuning outputs cannot pass this publication's frozen lock. The release deliberately refuses to replace its original approval with a new one. The archived original protocol implementation documents the development-time lock process; new scientific decisions require an explicitly separate protocol.

## Runtime record

The manuscript's development cost is based on `docs/tuning_report.md`: approximately 3.60 hours for irace and 4.88 hours for full-budget survivor checks. Earlier `results/timing_report_v2.csv` and `results/timing_summary_v2.md` retain a rough five-hour race estimate. Both are preserved as historical records; use the reconciled tuning report when interpreting the paper's development cost.

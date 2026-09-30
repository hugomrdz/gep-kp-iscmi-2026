# GEP-KP — ISCMI 2026

Reproduction package for **Evolving Interpretable Priority Rules for Hard 0–1 Knapsack Instances**, by Hugo Abel Moreno-Rodriguez and José Carlos Ortiz-Bayliss, ISCMI 2026.

Repository: <https://github.com/hugomrdz/gep-kp-iscmi-2026>

This repository contains the final `iscmi2026_v2` experiment, its frozen inputs and results, and the three corrected paper figures. The original scientific implementation, seeds, partitions, selected hyperparameters, and protocol approval are preserved. Four explicitly recorded packaging changes make the code work as a standalone repository.

## Quick start

The recorded environment uses Python **3.14.3**. Install Python 3.14 and run:

```bash
git clone https://github.com/hugomrdz/gep-kp-iscmi-2026.git
cd gep-kp-iscmi-2026
make setup
make test
make paper-figures
```

`make paper-figures` needs only the compact tables already in Git. It generates **fig01.pdf**, **fig02.pdf**, and **fig03.pdf** at the repository root, including the corrected panel labels, larger Figure 2 fonts, and tightly cropped Figure 1.

To restore the frozen benchmark archives and raw evaluations, then reproduce the statistics:

```bash
make fetch
make verify
make reproduce
make notebook
python3 scripts/check_reference_results.py
```

The prepared local distribution already contains these inputs. A fresh Git clone needs the `artifacts-v1` release assets. **The GitHub repository and release have not been published as part of this preparation.** Until the release is uploaded, restore from the supplied local bundles instead:

```bash
.venv/bin/python scripts/artifacts.py fetch all --source-dir /path/to/release-assets
```

See [artifact restoration and checksums](docs/artifacts.md) and [publication instructions](docs/publishing.md).

## What is included

| Location | Contents |
|---|---|
| `src/`, `tests/` | Training, independent decoding checks, evaluation, statistical analysis, and tests |
| `experiment_design_iscmi_v2.md` | Original experimental design |
| `protocol/` | Unmodified scientific lock, prelock review, implementation record, benchmark sources |
| `provenance/` | Explicit packaging changes and exact originals of adapted files |
| `tuning/` | irace scenario, runner, parameter space, five-survivor evidence and recovery records |
| `results/` | Frozen seeds, split, model genes, checkpoints, run records, and statistical summaries |
| `fig01.pdf`–`fig03.pdf` | Corrected conference-paper figures |
| `paper/build_figures.py` | Rebuilds the three conference-paper figures |
| `figures/`, `notebooks/` | Diagnostic plots and executed explanatory notebook |
| `data/` | Four original benchmark archives, restored from the data release asset |
| `release-assets/` | Local data and raw-evaluation bundles; excluded from Git |

Git contains compact scientific records, including individual run directories and tuning evidence. The approximately 2 GB of benchmark inputs and raw evaluations are distributed separately with file and bundle checksums. Caches, environments, machine-specific Jupyter installations, and obsolete submission templates are excluded.

## Reproduction levels

1. **Figures:** `make paper-figures` rebuilds the final PDFs from the published summary tables.
2. **Statistical results:** `make fetch`, `make verify`, and `make reproduce` rerun analysis from all raw evaluations, including all row permutations and transfer cases. Missing evaluations cause an error rather than a partial analysis.
3. **Final training and evaluation:** create an independent workspace that retains the frozen development decisions but contains no completed final runs:

```bash
.venv/bin/python scripts/new_replication.py ../gep-kp-iscmi-2026-replication
cd ../gep-kp-iscmi-2026-replication
make setup
make confirmatory WORKERS=4
make analyze
make notebook
make paper-figures
make verify
```

This last route recomputes the published final experiment and is expensive. The ordinary `make final-train` command is resumable, so running it in the supplied completed repository reuses validated run directories. The separate workspace prevents that reuse. See [reproduction details](docs/reproduction.md).

## Scientific reference points

The frozen split has 1,038 training, 345 validation, 345 ID-test, 1,249 OOD, and 263 unresolved cases. The four GEP terminal arms each have 75 final runs at a budget of 65,536 raw chromosome requests. The complete saved model matrix also includes matched random-search controls and the ISCMI experiment's historical continuity control.

| Method | Mean ID gap (ppm) |
|---|---:|
| BASE | 5,213.799 |
| CAP | 5,451.997 |
| SCALE | 5,050.212 |
| FULL | 4,905.632 |
| MAXPW | 7,695.286 |

The predeclared FULL-minus-BASE difference is −308.167 ppm, with a 95% bootstrap interval of [−640.372, 112.730] ppm. The declared practical-equivalence margin is ±872 ppm. Exact values are in `results/confirmatory/summary_v2.json`.

## Provenance and dependencies

`protocol/protocol_lock.json` is byte-for-byte the original approved lock. `provenance/publication_manifest.json` maps its 50 paths into this standalone layout and records the four adapted files: `Makefile`, `src/config.py`, `src/protocol.py`, and `tuning/target-runner`. Exact originals are archived under `provenance/original/`. The original historical V1 manifest is retained as evidence; this repository does not depend on, distribute, or claim to recheck that external experiment.

No source, data, result, template, or documentation was imported from the separate AHDAS repository. The `AHDAS_BASE` identifier already present in ISCMI V2 denotes its own 75-run continuity control and is retained so the published 675-model matrix remains intact. The code uses the same MIT license choice as that repository.

Python dependencies are pinned in `requirements.txt`; the original environment is recorded in `results/environment_v2.json`. R 4.6.1 and irace 4.4.3.9000 were used for tuning, as recorded in `tuning/R-packages.lock`. R is not required to regenerate figures or statistics from saved results.

## Citation and license

Citation metadata is in [CITATION.cff](CITATION.cff). The paper's DOI and proceedings pagination are not yet recorded here.

Original code and accompanying documentation are under the [MIT license](LICENSE). Third-party benchmark data is not relicensed by this repository. See [benchmark attribution](docs/data_sources.md) for the Jooken and Pisinger sources and citation information.

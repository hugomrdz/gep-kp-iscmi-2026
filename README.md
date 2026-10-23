# GEP-KP — ISCMI 2026

Code, results, and paper for **Beyond Fixed Greedy Rules: Evolving Interpretable Heuristics for Hard Knapsack Instances**, by Hugo Abel Moreno-Rodriguez and José Carlos Ortiz-Bayliss.

The [paper-v2 release](https://github.com/hugomrdz/gep-kp-iscmi-2026/releases/tag/paper-v2) contains the corrected paper submitted to ISCMI 2026, together with its code and results.

[Read the revised paper](iscmi2026_submission_HugoMoreno/VA280.pdf) · [LaTeX source and figures](iscmi2026_submission_HugoMoreno/) · [Changes from the original version](docs/revision_changes.md) · [Original paper](iscmi2026_HugoMoreno.pdf)

The knapsack problem asks which items to choose when each item has a profit and a weight, and the total weight must not exceed a limit. A simple approach is to sort items by a rule, such as profit divided by weight, and take each item if it still fits. We use gene expression programming (GEP), an evolutionary search method, to learn the formula used for that sorting step. The result is a short mathematical expression that can be read and reused on other instances.

The study asks whether these learned rules improve solution quality, whether giving them more information helps, and how well they work outside the conditions used for training. The repository includes the unsuccessful transfer results as well as the improvements.

## Get started

The paper, saved results, and [executed notebook](notebooks/gep_kp_iscmi2026_v2.ipynb) can be read without installing anything. To check the code and rebuild the figures, use Python 3.14 and R with the `class` package. The commands below use a Unix shell and `make`, as available on macOS, Linux, or Windows through WSL.

```sh
git clone https://github.com/hugomrdz/gep-kp-iscmi-2026.git
cd gep-kp-iscmi-2026
python3 --version
make setup
make test verify-provenance paper-figures
```

Check that `python3 --version` reports Python 3.14 before running `make setup`. Setup creates a local `.venv` environment; the commands use it automatically. R and `class` must be installed separately for the kNN tests.

This first check needs no benchmark download or training. It runs the tests, checks the original source fingerprints, and rebuilds `fig01.pdf`, `fig02.pdf`, and `fig03.pdf` from the saved tables. The instructions below cover the [additional comparison](#reproduce-the-comparison), [original experiment](#reproduce-the-original-experiment), and [paper build](#build-the-paper). The latest checks are recorded in [validation.md](docs/validation.md).

## What changed

The revised paper is **five pages, including references**, with all three figures and all five tables. The complete change record is in [revision_changes.md](docs/revision_changes.md). The main additions are:

- **More context for the approach.** The introduction now discusses four additional papers and explains the difference between selecting an existing rule, generating a new rule, and searching for a solution to one instance.
- **An additional comparison with kNN.** A nearest-neighbor classifier chooses among the four existing greedy rules. It uses the same 1,383 development instances as final GEP training and is evaluated on the same 345 ID and 1,249 OOD test instances. The four GEP formulae were already selected in the original experiment.
- **An expanded Table IV and a fuller interpretation.** The table identifies those four formulae and adds their ID mean gaps, the profit-to-weight rule (MAXPW), and kNN. The text reports uncertainty for all four formula-versus-kNN comparisons and explains where the results are inconclusive or favor kNN.
- **A clearer statistical statement.** The methods now state that practical equivalence requires the entire 90% interval to lie within the declared margin. This clarifies the original analysis; it does not recalculate it.
- **A self-contained paper package and reproduction record.** The new folder includes the LaTeX source, IEEE class, figures, final PDF, and build script. The comparison has its own fixed protocol, tests, saved predictions, per-instance results, and verification reports.

Some repeated explanations and examples were shortened to make room. The original training, tuning, 75-run results, figures, runtime table, item-order tests, unresolved cases, and Pisinger transfer analysis are preserved. This revision did not train new GEP models or run a new parameter search.

## Reading the results

An **ID** test instance uses problem sizes and capacities represented during development. An **OOD** instance uses a larger item count, a larger capacity, or both. Neither test set is used to fit the new comparator.

We measure the profit missing from the **certified optimum**, relative to that optimum, in parts per million (ppm). Lower is better: 0 means the solution is optimal, and 10,000 ppm means it is 1% below the optimum.

The original experiment evaluates four choices of information available to a formula: BASE uses normalized item profit, weight, and input position; CAP adds capacity information; SCALE adds a logarithmic profit feature; FULL includes both additions. Each choice has 75 final training runs. Their mean ID gaps remain:

| Original experiment, averaged over 75 runs | Mean ID gap (ppm) |
|---|---:|
| BASE | 5,213.799 |
| CAP | 5,451.997 |
| SCALE | 5,050.212 |
| FULL | 4,905.632 |

Although FULL has the lowest mean, FULL and BASE were practically equivalent within the declared margin of ±872 ppm. The original analysis therefore did not establish a meaningful benefit from adding both feature groups to BASE. The full results are in the [original summary table](results/confirmatory/method_summary_v2.csv).

The new comparison instead evaluates **one previously selected formula from each group**. These numbers answer a different question and should not be read as updated 75-run averages:

| Selected formula or comparison method | Mean ID gap (ppm) |
|---|---:|
| BASE-020 | 3,705.09 |
| CAP-008 | 3,656.68 |
| SCALE-042 | 4,403.73 |
| FULL-071 | 3,306.09 |
| MAXPW: sort by profit divided by weight | 7,695.29 |
| kNN: choose a greedy rule using the nearest development cases | 7,809.84 |

The [selected formulae](results/representative_expressions_v2.csv), [comparison summary](revision_comparison/results/evaluation/summary.csv), and [uncertainty intervals](revision_comparison/results/evaluation/id_contrasts.csv) are available as CSV files.

All four selected formulae have lower ID mean gaps than kNN. The adjusted uncertainty intervals support that difference for BASE, CAP, and FULL; the SCALE interval includes zero. kNN has a lower median ID gap than every selected formula, so the mean results do not imply that a learned formula wins on every instance. On the combined OOD cases, all four selected formulae have lower mean gaps than kNN, while kNN has a lower mean gap than MAXPW. The OOD comparisons are descriptive.

This is a reimplementation of the [2025 kNN method](https://doi.org/10.1016/j.patrec.2025.03.011) within our existing Jooken benchmark protocol. Its published experiment used a balanced synthetic training set; ours uses the original, unbalanced development set. The original limitations also remain: the benchmark had been inspected during earlier exploratory work, and the learned rules did not transfer successfully to the separate Pisinger collection. See [all nine methods, intervals, and limitations](revision_comparison/review/comparison_results.md).

## Find the files

| Location | What it contains |
|---|---|
| [iscmi2026_submission_HugoMoreno/](iscmi2026_submission_HugoMoreno/) | Revised paper, source, three figures, IEEE class, and build script |
| [revision_comparison/](revision_comparison/) | New comparison implementation, protocol, tests, and reproduction instructions |
| [revision_comparison/results/](revision_comparison/results/) | Development labels, test predictions, per-instance outcomes, summaries, and bootstrap samples |
| [revision_comparison/review/](revision_comparison/review/) | Manuscript diff, comparison results, and local verification records |
| `src/`, `tests/`, `tuning/` | Original scientific implementation, tests, and tuning evidence |
| `results/` | Original splits, seeds, model genes, run records, checkpoints, and summary results |
| `protocol/`, `provenance/` | Original experimental decisions, file fingerprints, and documented packaging changes |
| `paper/`, `figures/`, `notebooks/` | Figure builder, diagnostic plots, and executed explanatory notebook |
| [docs/](docs/) | Data attribution, artifact restoration, and detailed reproduction instructions |

The original uploaded PDF remains at `iscmi2026_HugoMoreno.pdf`. The roughly 2 GB of original benchmark inputs and raw evaluations remain in the unchanged [artifacts-v1 release](https://github.com/hugomrdz/gep-kp-iscmi-2026/releases/tag/artifacts-v1). The compact new comparison results are included directly in Git. Reference articles are linked, not redistributed as PDFs.

## Build the paper

Install Tectonic and Poppler, then run:

```sh
./iscmi2026_submission_HugoMoreno/build.sh
```

Run this from the repository root. The script produces `iscmi2026_submission_HugoMoreno/VA280.pdf`, using the source and figures in that folder, and checks that it has five pages. Tectonic may download its TeX packages on the first build. The script keeps temporary compilation files outside the folder. Python, R, and the benchmark downloads are not needed to build the paper. The saved PDF was also rebuilt from a separate copy of this folder and checked page by page; see the [verification report](revision_comparison/review/verification_report.md).

## Reproduce the comparison

After the setup above, use R 4.6.1 with class 7.3-23 and install Tectonic. The recorded revision environment uses Python 3.14.7 and Tectonic 0.17.0; see [environment.json](revision_comparison/environment.json). The comparison checks the pinned Python packages and exact R and `class` versions, so another R version can pass the unit tests but will be rejected by comparison verification. Tectonic is needed by this environment check even when no paper is being built.

```sh
make fetch
./v3.sh verify-inherited
./v3.sh verify
./v3.sh run --output revision_comparison/results/reproduction
./v3.sh verify --output revision_comparison/results/reproduction
```

`make fetch` downloads about 2 GB of original data and raw results and verifies their checksums. Allow at least 5 GB of free space for the bundles, restored files, and working outputs, in addition to the Python environment. An offline restoration option is documented in [artifacts.md](docs/artifacts.md). The comparison refuses to overwrite an existing output directory; use another unused path with `--output` for a later run. It reuses the four saved formulae and development labels, applies the methods to the test cases, and resamples the results to estimate uncertainty. It does not repeat the expensive evolutionary search. The development labels and protocol were fixed before the new test evaluation.

The [comparison instructions](revision_comparison/README.md) explain the three features, tie handling, seeds, grouped bootstrap, and saved outputs. `./v3.sh table` regenerates the standalone Table IV snippet from the recorded results; the manuscript already contains the table.

## Reproduce the original experiment

There are three levels of work:

1. **Regenerate figures:** after `make setup`, run `make paper-figures`. This reads the compact tables already in Git and writes `fig01.pdf`, `fig02.pdf`, and `fig03.pdf` at the repository root. The paper build uses its saved copies in the submission folder.
2. **Recompute statistics from saved evaluations:** run `make fetch`, `make verify`, `make reproduce`, `make notebook`, and `python3 scripts/check_reference_results.py`. This includes the original item-order and transfer analyses. Missing evaluations cause an error.
3. **Train and evaluate again:** create an independent replication workspace with `scripts/new_replication.py` and follow [reproduction.md](docs/reproduction.md). This can take many hours. Running a resumable training command in the completed repository would reuse its saved runs.

The original run used Python 3.14.3; its environment is retained in `results/environment_v2.json`. The original tuning used R and irace, but neither tuning nor new training is needed to inspect the paper or reproduce the additional comparison. R is required for the new kNN tests and evaluation, not for regenerating the original figures or statistics.

## Provenance, citation, and license

The original scientific lock is unchanged. `provenance/publication_manifest.json` records the existing four standalone packaging adaptations and preserves their original files. The new comparison has a separate [frozen protocol](revision_comparison/frozen_protocol.json), including source, input, development-data, and selected-model fingerprints. Historical `_v2` filenames and model identifiers are retained so earlier results remain traceable.

The `AHDAS_BASE` name in the original results is an ISCMI continuity control. It does not refer to a new experiment imported from the separate AHDAS repository.

Citation metadata is in [CITATION.cff](CITATION.cff). The paper's DOI and proceedings pagination are not yet recorded here. Original code and documentation use the [MIT license](LICENSE); third-party benchmark data retains its original attribution and terms. See [data_sources.md](docs/data_sources.md).

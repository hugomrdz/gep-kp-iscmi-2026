# Revision comparison: selected GEP formulae and kNN

This additional analysis reimplements Zárate-Aranda and Ortiz-Bayliss (2025) under the existing Jooken protocol. It is conditional on the four previously development-selected formulae, not a replacement for the original 75-run experiment. No GEP training, hyperparameter search, or new benchmark generation is performed. Small unit-test fixtures are not experimental data.

## Reproduce

From the repository/V3 root, install Python 3.14, R with package `class`, Tectonic, and Poppler. The recorded versions are in [environment.json](environment.json). The original Python pins are unchanged:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./v3.sh test
./v3.sh verify-inherited
./v3.sh verify
./v3.sh table
./v3.sh paper
```

In the public repository, first restore the unchanged `artifacts-v1` inputs with `make fetch` (see the existing artifact documentation). The author V3 copy already contains them. To recompute the additional study without replacing the reviewed results:

```sh
./v3.sh run --output revision_comparison/results/reproduction
./v3.sh verify --output revision_comparison/results/reproduction
```

`run` refuses existing output directories. Scientific outcomes, features, predictions, summaries, and bootstrap samples should agree; timings and run manifests will differ. `./v3.sh table` regenerates `revision_comparison/table_iv.tex` from the reviewed results. The manuscript embeds that table so the submission package needs no external file.

The historical sequence was `./v3.sh prepare`, tests, `./v3.sh freeze`, `./v3.sh run`, `./v3.sh verify`, then `./v3.sh table`. `prepare` reads only training/validation cases. `freeze` records protocol, source, input, selected-gene, development-artifact, and runtime hashes before test evaluation. These commands refuse to overwrite the existing development artifacts or lock. Preserve this freeze when reproducing the study.

## Protocol and implementation

See [protocol.json](protocol.json), [frozen_protocol.json](frozen_protocol.json), [core.py](core.py), [predict.R](predict.R), and [tests](tests/).

Features are mean profit/max profit, mean weight/max weight, and `(Pearson(profit,weight)+1)/2`, computed once per instance without dataset-level scaling. Undefined correlation uses rho=0 (feature 0.5); finite correlation is clipped only for rounding. No real development/test case required this fallback.

The 1,383 original train-plus-validation cases supply labels from the four unchanged greedy rules and decoder. Integer-profit ties use DEF, MAXP, MAXPW, MINW order. Label counts are 5, 486, 742, and 150; 65 cases have equal-profit label ties. This distribution differs materially from the published balanced synthetic training distribution. No rebalancing is applied.

R `class::knn` uses k=1, l=0, Euclidean distance, `use.all=TRUE`, and seed 20261021 (Mersenne-Twister/Inversion/Rejection). Training and the single combined 1,594-row test matrix use ascending ASCII instance names. All tied nearest neighbors vote; equal class votes are broken by R's seeded RNG. `prob=TRUE` records the winning vote fraction and does not change classification. Predictions are repeated in a fresh R process and checked for equality.

The unchanged BASE-020, CAP-008, SCALE-042, and FULL-071 genes are applied through the copied parser and decoder, alongside DEF, MAXP, MAXPW, MINW, and kNN. Test coverage is 345 ID, 432 OOD-n, 667 OOD-c, and 150 OOD-nc instances. Existing permutation, unresolved, and Pisinger analyses are untouched.

For ID, all four formula-minus-kNN contrasts use 10,000 resamples of 115 complete three-sibling groups, seed 20261022, NumPy PCG64. Percentile endpoints at .00625 and .99375 provide Bonferroni-adjusted 98.75% intervals for the four two-sided contrasts. Models are fixed, so no run-level resampling is added. OOD summaries are descriptive case-weighted means; no additional OOD significance tests are made.

## Saved evidence

- `results/development_*`: all development features, labels, tie information, rule outcomes, and timing.
- `results/evaluation/test_features.csv`, `predictions*.csv`: all test features and reproducible predictions.
- `outcomes.csv.gz`, `feasibility_checks.csv.gz`: all 14,346 method-instance outcomes and integer checks.
- `summary.csv`: all nine methods in ID, every OOD region, and pooled OOD.
- `id_group_differences.csv`, `bootstrap_replicates.csv.gz`, `id_contrasts.csv`: complete grouped inference.
- `decode_timings.csv.gz`, `timing_metadata.json`, `r_session*.txt`: descriptive timing and R environment. Formula timings include scoring; fixed-rule timings exclude score construction; no speed superiority is claimed.
- `original_replay_verification.json`: all 12,752 original method-instance pairs agree exactly in integer profit, packed weight, and optimum.
- `run_manifest.json`: hashes of all evaluation artifacts, bound to the frozen protocol.

See [comparison results](review/comparison_results.md), [changes from the original version](../docs/revision_changes.md), and [verification report](review/verification_report.md).

## Reference links

- [Zárate-Aranda and Ortiz-Bayliss (2025)](https://doi.org/10.1016/j.patrec.2025.03.011): classifier selection of existing greedy rules.
- [Dokeroglu, Kucukyilmaz, and Talbi (2024)](https://doi.org/10.1016/j.cie.2023.109815): taxonomy and broader field.
- [Liu et al. (2024), official ICML/PMLR proceedings](https://proceedings.mlr.press/v235/liu24bs.html): evolution of natural-language ideas and executable heuristic code; no DOI is listed in the proceedings record.
- [Jooken et al. (2023)](https://doi.org/10.1016/j.cor.2022.106070): per-instance adapted MCTS. The supplied PDF is an author manuscript; the paper cites the published journal article.
- [R class::knn documentation](https://stat.ethz.ch/R-manual/R-devel/library/class/html/knn.html): classifier defaults and tie behavior.

Third-party article PDFs are not included in the public repository update.

# Changes from the original uploaded version

This record compares the revised [five-page paper](../iscmi2026_submission_HugoMoreno/VA280.pdf) with the [original uploaded PDF](../iscmi2026_HugoMoreno.pdf), and describes the accompanying repository additions. The exact LaTeX changes are available in [manuscript.diff](../revision_comparison/review/manuscript.diff).

## Paper

| Part | Change |
|---|---|
| Introduction | Replaced the brief related-work paragraph with a discussion of four additional papers. It distinguishes choosing an existing heuristic, generating a reusable formula or algorithm, and searching for a solution to an individual instance. |
| II-D: Tuning, Training, and Statistics | Added the kNN comparison protocol: development data, features, classifier, tie handling, fixed selected formulae, seeds, and statistical comparison. Clarified that practical equivalence requires the entire 90% interval to fall inside the existing ±872 ppm margin. |
| III-A: Results and Table IV | Added the identifiers BASE-020, CAP-008, SCALE-042, and FULL-071 and their ID mean gaps. Added MAXPW and kNN rows. Reported all four formula-minus-kNN contrasts with adjusted intervals, and summarized the combined OOD results. Explained that these are individual selected formulae, separate from the original averages over 75 training runs. |
| Discussion and conclusion | Qualified the new evidence: three adjusted ID intervals favor the selected formulae, SCALE remains inconclusive, and kNN has the better ID median. The comparison uses our original development distribution, which differs from the balanced training distribution in the published kNN study. |
| References | Added four entries, retained the original reference identities, and ordered the manual IEEE bibliography by first citation. The bibliography now has 13 entries. |
| Length | Removed the section roadmap, a survivor-ranking anecdote, a seed-pairing example, and repeated values or interpretations. The final paper remains five pages, including figures, tables, and references, without reducing the prescribed layout or typography. |

The four added references serve different purposes:

- [Zárate-Aranda and Ortiz-Bayliss (2025)](https://doi.org/10.1016/j.patrec.2025.03.011) provides the kNN method for choosing among greedy knapsack rules.
- [Dokeroglu, Kucukyilmaz, and Talbi (2024)](https://doi.org/10.1016/j.cie.2023.109815) provides the broader classification of hyper-heuristics.
- [Liu et al. (2024)](https://proceedings.mlr.press/v235/liu24bs.html) gives context for generating heuristics with language models. The citation follows the official ICML proceedings record, without adding a DOI.
- [Jooken et al. (2023)](https://doi.org/10.1016/j.cor.2022.106070) provides a comparison in scope: its adapted Monte Carlo tree search searches within individual instances. The citation names the published journal article.

The title, authors, abstract, keywords, research questions, and section structure remain the same. Sections II-A–II-C and III-B–III-C, Tables I–III and V, all three figure PDFs, and the supplied IEEE class are unchanged. The original numerical findings, runtime table, item-order results, unresolved cases, and transfer limitations are retained.

## Additional comparison

The new [revision_comparison/](../revision_comparison/) package evaluates the four previously selected GEP formulae, four fixed greedy rules, and kNN. It uses 1,383 development instances, 345 ID test instances, and 1,249 OOD test instances from the original split. There is no new GEP training, parameter search, or generated benchmark data.

kNN uses three normalized instance features and R `class::knn` with `k = 1`. Each development instance receives the label of the greedy rule that produces the largest profit; equal profits use the existing fixed rule order. The protocol records undefined-correlation handling, nearest-neighbor ties, stable instance ordering, and seed 20261021. Source and input fingerprints were frozen before the test evaluation.

All four ID comparisons resample the 115 sibling groups together, keeping related instances in the same group. They use 10,000 bootstrap samples, seed 20261022, and Bonferroni-adjusted 98.75% intervals. The formulae remain fixed throughout this analysis. All four contrasts are reported, including the interval that crosses zero. The [results report](../revision_comparison/review/comparison_results.md) includes means, medians, exact-solution rates, and each OOD region for all nine methods.

Saved evidence includes development features and labels, test features, repeated kNN predictions, 14,346 method-instance outcomes, feasibility checks, timing records, summary tables, all bootstrap samples, and file fingerprints. Replayed formula and fixed-rule results match all 12,752 original method-instance outcomes in integer profit, packed weight, and certified optimum.

New tests cover feature calculations, undefined and constant features, ties, reproducible predictions, separation of development and test instances, and grouped resampling. The public repository's test workflow now installs R and `class` so these tests run with the existing suite.

## Files and reproduction

- Added `iscmi2026_submission_HugoMoreno/` with exactly seven files: `manuscript.tex`, `IEEEtran.cls`, `fig01.pdf`, `fig02.pdf`, `fig03.pdf`, `VA280.pdf`, and `build.sh`. All source references are local to that folder. The build script keeps temporary files elsewhere and checks the five-page count.
- Added `v3.sh` for the comparison, tests, verification, table generation, and paper build. Its reproduction output is separate from the recorded results.
- Added the comparison's fixed protocol, environment record, source and input hashes, tests, compact results, manuscript diff, and verification reports.
- Added a path adapter for the original scientific lock and a snapshot of the parent experimental-design document. The original lock and existing public packaging adaptations remain intact.
- Rewrote the README to explain the problem, distinguish the original experiment from the additional comparison, and provide separate instructions for reading the results, building the paper, recomputing the comparison, and repeating the original training.
- Kept the original uploaded PDF and the `artifacts-v1` release. The new compact results are tracked in Git; the existing benchmark and raw-result bundles are unchanged. Git ignore rules cover reproduction outputs and retain the verification logs.

The author workspace was prepared as an independent V3 copy. Its copied caches and Jupyter configuration were replaced with local equivalents, and only `ApproxCO_2011.pdf` was removed from its article collection. The other four reference PDFs remain in that local workspace; the public repository distributes citation links. These workspace changes and the final V2 fingerprint check are documented in [cleanup_list.md](../revision_comparison/review/cleanup_list.md).

The [verification report](../revision_comparison/review/verification_report.md) records the scientific checks, 45 passing public-repository tests, five-page PDF inspection, embedded fonts, and a successful build from a separate copy of the submission folder. These are local checks of the package.

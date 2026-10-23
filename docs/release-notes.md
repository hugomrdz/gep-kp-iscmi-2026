# Corrected conference paper (paper-v2)

This release accompanies the corrected paper submitted to ISCMI 2026, “Beyond Fixed Greedy Rules: Evolving Interpretable Heuristics for Hard Knapsack Instances.”

- Includes the [submitted five-page PDF](../iscmi2026_submission_HugoMoreno/VA280.pdf), its LaTeX source, figures, and build script.
- Includes the additional kNN comparison, using the four previously selected GEP formulae and the original development and test sets.
- Updates the README and reproduction instructions to match the corrected paper and help readers get started.
- Records 45 passing tests, verified source and data fingerprints, an exact reproduction of the additional comparison, and a paper rebuild matching all five saved pages.

The original training results and frozen experimental records are unchanged. The benchmark inputs and raw evaluations remain available in the [artifacts-v1 release](https://github.com/hugomrdz/gep-kp-iscmi-2026/releases/tag/artifacts-v1). See the [change record](revision_changes.md) and [validation record](validation.md) for details.

## Frozen reproduction inputs (artifacts-v1)

Frozen reproduction inputs for the original ISCMI 2026 experiment.

- `data.tar`: the exact Jooken and Pisinger benchmark archives used by the experiment.
- `results.tar`: original Jooken evaluations, ten row-order permutation files, and Pisinger transfer evaluations.

Download/restore with `python scripts/artifacts.py fetch all`. The script checks SHA-256 fingerprints for each bundle and every member before installation. Compact results, source, frozen protocol, trained model records, and corrected paper figures are in the Git repository.

Third-party benchmarks retain their original attribution and terms; see `docs/data_sources.md`. The repository's MIT license applies to its original software and documentation.

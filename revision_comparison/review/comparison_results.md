# Additional comparison results

Lower mean residual gap is better. These are four fixed, previously development-selected formulae, not the 75-run arm averages in the original experiment. The comparator reimplements the 2025 kNN method using its published features and R classifier under the existing Jooken partitions. It is not a replication of the published balanced synthetic benchmark.

| Method | ID mean ppm | ID median ppm | ID exact % | OOD-n mean ppm | OOD-c mean ppm | OOD-nc mean ppm | Pooled OOD mean ppm |
|---|---:|---:|---:|---:|---:|---:|---:|
| BASE-020 | 3,705.09 | 1,911.01 | 25.22 | 3,617.46 | 3,701.15 | 3,436.44 | 3,640.41 |
| CAP-008 | 3,656.68 | 1,713.23 | 25.22 | 4,823.25 | 2,753.73 | 2,998.19 | 3,498.89 |
| SCALE-042 | 4,403.73 | 1,682.22 | 0.00 | 5,303.39 | 2,379.55 | 2,564.12 | 3,413.01 |
| FULL-071 | 3,306.09 | 781.70 | 25.22 | 2,745.05 | 3,833.53 | 4,177.60 | 3,498.37 |
| DEF | 11,514.55 | 4,648.24 | 0.00 | 12,341.06 | 10,747.21 | 11,860.47 | 11,432.18 |
| MAXP | 11,114.30 | 4,563.29 | 25.22 | 11,547.76 | 10,747.19 | 11,860.46 | 11,157.79 |
| MAXPW | 7,695.29 | 77.99 | 4.93 | 8,145.17 | 11,041.76 | 12,310.64 | 10,192.28 |
| MINW | 18,089.95 | 4,886.05 | 0.00 | 18,288.29 | 9,772.43 | 9,851.26 | 12,727.34 |
| kNN | 7,809.84 | 46.94 | 25.22 | 7,415.97 | 9,095.94 | 9,517.16 | 8,565.46 |

ID contains 345 cases in 115 complete sibling groups. OOD-n/c/nc contain 432/667/150 cases; pooled OOD contains 1,249 cases. All means weight instances equally. Some OOD groups have fewer than three certified siblings; no OOD bootstrap or complete-sibling assumption is applied there.

| ID contrast | Mean difference ppm | Bonferroni-adjusted 98.75% interval ppm |
|---|---:|---:|
| BASE-020 - kNN | -4,104.76 | [-7,907.48, -827.00] |
| CAP-008 - kNN | -4,153.16 | [-8,445.98, -493.72] |
| SCALE-042 - kNN | -3,406.11 | [-7,858.86, 409.37] |
| FULL-071 - kNN | -4,503.75 | [-8,354.65, -1,174.13] |

All four contrasts are reported. BASE, CAP, and FULL have intervals below zero. SCALE's interval includes zero, so the comparison does not establish its mean advantage under this adjustment. The bootstrap uses 10,000 resamples of the 115 groups (all three siblings together), seed 20261022, and holds the selected models fixed.

kNN has a much lower ID median than any selected formula. It also has the same ID exact-solution rate as BASE, CAP, FULL, and MAXP, and exceeds SCALE's exact rate. On pooled OOD its mean is lower than MAXPW's, while all four selected formulae have lower means than both. These descriptive comparisons do not establish dominance on individual cases or a universal method ranking. No additional significance tests were performed for kNN versus MAXPW or for OOD regions.

The 1,383 development labels are DEF 5, MAXP 486, MAXPW 742, and MINW 150, with 65 equal-profit label ties resolved by the frozen rule order. The published training set was balanced across rule labels. This difference and the prior Jooken benchmark inspection limit the scope of the comparison.

All 14,346 evaluated solutions are feasible and do not exceed certified optima. All 12,752 formula/fixed-rule profits, packed weights, and optima match the original saved evaluations exactly. No permutation, unresolved-case, or Pisinger result was recalculated or replaced. The original zero-shot transfer failure remains in the paper.

Full precision, per-instance data, and all bootstrap draws are in [the results folder](../results/evaluation/). Timing records are descriptive: they include different components for formula and fixed-rule calls and do not support a comparative speed claim.

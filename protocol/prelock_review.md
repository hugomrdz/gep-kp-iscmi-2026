# Pre-lock review: ISCMI 2026 GEP-KP V2

**Status:** awaiting author/advisor approval  
**Prepared:** 2026-08-29  
**Test access:** closed; `protocol_lock.json` does not exist

## Proposed common configuration

The frozen selection rule chooses `irace_04`, corresponding to original irace
configuration 10:

| Parameter | Selected value |
|---|---:|
| Head length | 10 |
| Population | 512 |
| Tournament size | 7 |
| Elite fraction | 0.01 |
| Crossover rate | 0.70 |
| Expected mutations per chromosome | 3 |
| Confirmatory raw-request budget | 65,536 |

## Why this configuration won

All five main-race elites were rerun with 10 fresh paired seeds under all four
terminal arms at the full 65,536-request budget. This produced exactly 200
unique survivor cells. Lower rank and lower gap are better.

| Order | Candidate | Mean paired validation rank | Pooled validation gap (ppm) | Worst-arm gap (ppm) |
|---:|---|---:|---:|---:|
| 1 | `irace_04` | 2.5750 | 5,485.566 | 5,810.768 |
| 2 | `irace_03` | 2.5750 | 5,555.413 | 5,935.536 |
| 3 | `irace_02` | 2.8125 | 5,539.786 | 5,876.117 |
| 4 | `irace_05` | 2.9000 | 5,672.310 | 6,181.297 |
| 5 | `irace_01` | 4.1375 | 6,907.797 | 7,130.092 |

`irace_04` and `irace_03` tied on the primary mean-rank criterion. `irace_04`
won the first predeclared tie-break because its pooled validation gap was lower.
No later tie-break was needed.

This full-budget screen mattered. `irace_04` was only fourth in the main
16,384-request race and did not enter irace's optional top-three
post-selection. Keeping all five predeclared survivors avoided choosing from a
premature reduced-budget shortlist.

Per-arm validation gaps for the proposed winner are:

| Arm | Mean gap (ppm) |
|---|---:|
| `BASE` | 5,810.768 |
| `CAP` | 5,358.430 |
| `SCALE` | 5,253.567 |
| `FULL` | 5,519.499 |

These are development results. They do not answer the confirmatory research
questions and must not be presented as test performance.

## Gate checks completed

- 2,000 irace target evaluations completed with seed `20260902`.
- Five main-race elites exported; optional three-way post-selection preserved
  separately.
- 200/200 full-budget survivor cells present, unique, and atomically valid.
- 19/19 implementation tests pass.
- 35/35 historical V1 files match the history manifest.
- Jooken archive SHA-256 matches the frozen source.
- 31,800/31,800 Pisinger certificates pass; all 31,800 cases are byte-distinct.
- Train/validation/test split, seeds, permutations, power plan, analysis code,
  and figure specification are ready to enter the signed lock.
- No ID, OOD, unresolved, row-permutation, or Pisinger model evaluation has
  been generated.

## Approval action

If the author and advisor accept this configuration and the frozen protocol,
create the signed lock with a real approver name:

```bash
make -C iscmi2026_v2 lock-protocol APPROVER="name reviewed with advisor"
```

Do not run `confirmatory`, `final-train`, `evaluate`, or `analyze` before that
review. Once the lock exists, source/code changes require an amendment and rerun
of every affected arm.

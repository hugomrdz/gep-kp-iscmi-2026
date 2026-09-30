# V2 implementation log

This is the pre-lock engineering record. Post-lock corrections belong in
`amendments.md` and require a new lock plus reruns of every affected arm.

## 2026-08-28

- Created `experiment_design_iscmi_v2.md` and the independent
  `iscmi2026_v2/` tree.
- Generated `history_manifest.sha256` for the historical protocol, V1 source,
  old results, and old publication figures. The V1 audit currently covers 35
  unchanged files.
- Copied the Jooken archive from V1 and verified SHA-256
  `68ef9b6be17fbc37f303a250aa79cacfcbe7167d5f0b83f8f96c60d666f0fb26`.
- Built the two-stage group-random split: 1,038 train, 345 validation, 345 ID,
  432 OOD-n, 667 OOD-c, 150 OOD-nc, and 263 unresolved.
- Implemented and audited `BASE`, `CAP`, `SCALE`, and `FULL`, the exact raw
  request checkpoints, separate RNG streams, matched random search, the
  accepted 21,280-request AHDAS continuity control, deterministic baselines,
  and the validation-selected power ranker.
- Installed R 4.6.1 and `irace` 4.4.3.9000. The official `checkIraceScenario`
  preflight passed after changing the target runner to an explicit project-venv
  wrapper.
- Started the full 2,000-experiment blocked irace run with seed `20260902`.
- Recovered an interrupted irace process from its end-of-iteration checkpoint
  into a separate `irace_recovered.Rdata` log, preserving the saved RNG state.
  The completed race used exactly 2,000 target evaluations. Its final five
  main-race elites are configurations 46, 39, 49, 10, and 2. The optional
  post-selection ranked 46, 39, and 49; it is recorded separately and does not
  replace the predeclared five-candidate full-budget survivor stage.
- Downloaded all three official Pisinger archives from David Pisinger's
  University of Copenhagen page. The streaming audit verified all 31,800
  supplied solution vectors against capacity and stated optimum. It retained
  all 31,800 byte-distinct cases: 10,400 small-coefficient, 16,000
  large-coefficient, and 5,400 hard instances. Exact source fingerprints and
  family counts are recorded in `pisinger_sources.md`.
- Added atomic per-run CSV/JSON records, final merges, guarded protocol locking,
  frozen test evaluation, 60-second HiGHS attempts, crossed bootstrap analysis,
  publication figures, and the advisor notebook.
- Installed a project-local Jupyter kernel named `iscmi2026-v2`; the notebook
  enforces `.venv` and uses only `$...$` and `$$...$$` math delimiters.
- The current semantic, parser, budget, atomic-I/O, ranking, analysis, and
  notebook suite passes 19 tests, including headless PDF/SVG/PNG export.

## 2026-08-29

- Completed the five-by-four-by-ten full-budget survivor matrix: 200 unique
  candidate/arm/run cells, each at 65,536 raw requests and evaluated on the
  frozen validation partition.
- Selected `irace_04` (original irace configuration 10) by the predeclared
  rule. It tied `irace_03` on mean paired validation rank at 2.575, then won
  the first tie-break with pooled validation gap 5,485.566 ppm versus
  5,555.413 ppm. Its worst-arm validation gap is 5,810.768 ppm.
- The selected common setup is head length 10, population 512, tournament 7,
  elite fraction 0.01, crossover 0.70, and three expected mutations per
  chromosome. The confirmatory raw-request budget remains 65,536.
- The winner was fourth among the five main-race elites and was not in the
  optional three-configuration irace post-selection. The predeclared
  independent full-budget survivor stage therefore materially changed the
  choice; no post-selection result was used to censor the five candidates.
- Re-ran the Pisinger streaming audit under the frozen archive byte sizes and
  SHA-256 fingerprints. The deterministic manifest hash remained
  `87a5320f3125f9b023aa34b63b6b5b1bb496e2a9e7e9fbf3025d7c3dcc257654`.
- Re-ran the 19-test suite and the pre-lock verifier. All tests pass, all 200
  atomic survivor directories validate, all 35 V1 files remain unchanged, and
  all 31,800 transfer certificates validate. No protocol lock or confirmatory
  evaluation exists yet.

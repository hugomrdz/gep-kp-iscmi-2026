# ISCMI 2026 GEP-KP confirmatory experiment — protocol V2

**Protocol version:** 2.0  
**Protocol date:** 2026-08-28  
**Implementation:** `iscmi2026_v2/`  
**Historical protocol:** `experiment_design_iscmi.md` and `iscmi2026/` (read-only)

## 1. Status and scientific boundary

The first Jooken experiment is pilot evidence. It used a deterministic factor-level split, a small search budget, 30 runs, two locally designed terminal alphabets crossed with two objectives, and analysis code that could accidentally emphasize one run. V2 is a new, protocol-locked experiment. It does not overwrite or reinterpret the old CSV files.

The Jooken collection is not pristine blind data for this project: its structure and earlier results influenced the new terminals. The ID and OOD results are therefore protocol-locked confirmation on a previously inspected benchmark. Frozen transfer to Pisinger's established classes supplies the external test.

The exact `BASE`, `CAP`, `SCALE`, and `FULL` alphabets are our contribution. Prior GP and hyper-heuristic research supports normalized state-descriptive terminals and held-out evaluation; it does not prescribe these exact features.

## 2. Research questions and estimands

- **RQ1 — representation:** Does `FULL` reduce mean ID optimality gap relative to `BASE`?
- **RQ2 — feature ablation:** Are capacity and scale features individually necessary?
- **RQ3 — generalization:** Do effects persist under new item-count and capacity levels and on Pisinger classes?
- **RQ4 — budget:** Are conclusions stable at 1,872, 4,096, 16,384, 21,280, 32,768, and 65,536 raw requests?
- **RQ5 — discovery:** Does GEP discover behavior beyond MAXPW and a two-parameter density ranker?

For certified optimum $O_i$ and heuristic profit $H_i$, define

$$
g_i=10^6\frac{O_i-H_i}{O_i}.
$$

The primary endpoint is mean $g_i$ on the 345-case ID test. Lower is better. The primary paired contrast is `FULL - BASE`; negative values favor `FULL`.

MAXPW's pilot residual gap was approximately 8,720 ppm. The predeclared smallest effect of interest is

$$
\Delta_{\mathrm{SESOI}}=0.10(8720)=872\ \text{ppm}.
$$

## 3. Jooken data and locked split

The published archive contains 3,240 cases: 2,977 with certified optima and 263 unresolved by the supplied run.

### 3.1 In-distribution pool

The ID pool contains the 1,728 certified cases with $n\in\{400,600,800,1000\}$ and $c\in\{10^6,10^8\}$. Define a group by `(n,c,g,f,eps)` and keep its three `s` siblings together.

Using PCG64 seed `20260901`, assign the 576 groups with a two-stage mixed-integer allocator. Stage one minimizes normalized absolute marginal imbalance over `n,c,g,f,eps` subject to exact partition sizes. Stage two retains the optimal imbalance and uses seeded random ranks to choose one solution. The resulting split is random at group level, reproducible, and marginally balanced.

| Partition | Groups | Cases | Use |
|---|---:|---:|---|
| Train | 346 | 1,038 | Evolution and candidate fitness |
| Validation | 115 | 345 | Tuning and model-selection decisions |
| ID test | 115 | 345 | Locked confirmatory endpoint |

### 3.2 Extrapolation sets

| Partition | Definition | Certified cases |
|---|---|---:|
| OOD-$n$ | $n=1200$, $c\in\{10^6,10^8\}$ | 432 |
| OOD-$c$ | $n\in\{400,600,800,1000\}$, $c=10^{10}$ | 667 |
| OOD-$nc$ | $n=1200$, $c=10^{10}$ | 150 |

These counts exhaust the certified collection:

$$
1038+345+345+432+667+150=2977.
$$

The 263 unresolved cases are evaluated separately. They receive feasibility, raw-profit, and win/tie/loss summaries. A fixed single-threaded HiGHS attempt gets 60 seconds per case; lower or upper bounds are never called optima unless the solver certifies them.

### 3.3 Row-order audit

For every locked test case, generate ten deterministic item-row permutations from seed `20260905`. Preserve item identity, profit, weight, capacity, and optimum; recompute `O`. All methods and runs receive identical permutations.

The row-order audit evaluates the final checkpoint of every frozen stochastic
model plus each deterministic rule. Original-order evaluation retains every
budget checkpoint. This tests all 75 runs per arm without treating ten row
orders as ten new problem instances.

## 4. External Pisinger transfer

Obtain the small-coefficient, large-coefficient, and hard-instance archives and their supplied solutions from David Pisinger's academic code page. Their frozen SHA-256 fingerprints and byte sizes are recorded in `iscmi2026_v2/protocol/pisinger_sources.md`. Parse every certified case, retain archive/class/size/range/capacity metadata, and remove only byte-equivalent duplicates. The audited archives contain 10,400 small-coefficient, 16,000 large-coefficient, and 5,400 hard cases (31,800 total); all 31,800 supplied certificates pass and all cases are byte-distinct, so none are removed.

The Jooken-trained genes, parameter ranker, and representative-expression rule are frozen before any Pisinger score is calculated. Pisinger results cannot select terminals, hyperparameters, seeds, expressions, or reporting thresholds.

The transfer evaluation uses the final checkpoint of all 675 frozen stochastic
models: 300 GEP, 300 matched random-search, and 75 `AHDAS_BASE` continuity
models. Each supplied Pisinger solution vector is checked for feasibility and
exact agreement with its stated optimum before the case enters the manifest.

## 5. Representation ablation

For item $i$:

$$
P_i=\frac{p_i}{\max_j p_j},\quad
W_i=\frac{w_i}{\max_j w_j},\quad
O_i=1-\frac{i}{\max(n-1,1)},
$$

$$
K_i=\frac{w_i}{c},\quad
T=\frac{c}{\sum_j w_j},\quad
L_i=\frac{\log(1+p_i)}{\max_j\log(1+p_j)}.
$$

| Arm | Terminals | Hypothesis |
|---|---|---|
| `BASE` | `P W O 1 0` | Accepted representation |
| `CAP` | `P W O K T 1 0` | Capacity information helps |
| `SCALE` | `P W O L 1 0` | Log-scale information helps |
| `FULL` | `P W O K T L 1 0` | Both groups help, including interaction |

This is a $2\times2$ information-package ablation. Different alphabet sizes are part of the system comparison, so matched uniform random-gene search is required as a branching-factor sensitivity control.

## 6. Search semantics and objective

- One chromosome, one GEP gene, one static item-priority expression.
- Functions: `+`, `-`, `*`, protected division.
- Protected division returns 1 when denominator magnitude is at most $10^{-12}$.
- NaN maps to $-10^9$; infinities map to $\pm10^9$; scores are clipped to that range.
- Stable descending score sort; original row position breaks ties.
- One feasibility-preserving scan packs the ordered items.
- Raw expressed ORF is the cache key.
- No optimum, solution membership, or generator label is a terminal.

Evolution lexicographically minimizes

$$
\left(\frac{1}{|S|}\sum_{i\in S}g_i,\ |\operatorname{ORF}|\right).
$$

ORF length is only a numerical tie-break. Strict integer exactness remains a secondary metric.

## 7. Budget, tuning, and repetitions

Maximum budget is 65,536 raw chromosome requests. Checkpoints are 1,872; 4,096; 16,384; 21,280; 32,768; and 65,536. Cached requests still count as raw requests; unique ORFs, candidate-instance evaluations, and time are also recorded. Confirmatory runs never stop early.

Configure one common evolutionary setup on train/validation only:

| Parameter | Search values |
|---|---|
| Head length | `{6,8,10,12}` |
| Tail | `h+1` |
| Population | `{128,256,512}` |
| Tournament | `{2,4,7}` |
| Elite fraction | `{0.5%,1%,2%}`, ceiling, minimum one |
| Crossover | `{0.50,0.70,0.90}` |
| Expected mutations | `{1,2,3}` per chromosome |

Use irace with `maxExperiments=2000` at 16,384 requests. Terminal arm, one of four balanced training folds, and evolutionary seed are scenario factors. Re-evaluate five survivors at 65,536 requests with ten fresh paired seeds and all four arms. Select one common setup by mean validation rank; deterministic tie-breaks are pooled validation gap, worst-arm gap, then the ordered parameter tuple.

After tuning, train 75 paired runs for each terminal arm on train plus validation. SeedSequence-derived streams independently control initialization, selection, crossover, and mutation.

The power basis is pilot paired SD 2,192 ppm, SESOI 872 ppm, approximate paired effect 0.40, 80% power, and multiplicity near $0.05/3$. This requires roughly 67 runs; 75 provides margin for failures and non-normality.

## 8. Controls

- DEF, MAXP, MAXPW, and MINW.
- `AHDAS_BASE`: accepted historical configuration at 21,280 requests, labelled as continuity rather than a confirmatory arm.
- Uniform valid-gene random search for each alphabet, with the same seeds, budgets, and checkpoints as GEP.
- $P^\alpha/W^\beta$, with $\alpha,\beta\in\{0,0.25,\ldots,3\}$ selected on validation and `(0,0)` excluded.

Deterministic methods are evaluated once per instance/permutation. They are not copied 75 times and treated as independent.

## 9. Metrics and confirmatory statistics

Report mean, median, 90th percentile, CVaR$_{0.90}$, worst gap, strict exact rate, feasibility, MAXPW gap closure, win/tie/loss, train-to-test change, runtime, raw requests, unique ORFs, candidate-instance evaluations, ORF length, and ranking equivalence.

Predeclared contrasts:

1. `FULL - BASE` on ID mean gap, primary, $\alpha=0.05$.
2. `FULL - CAP`, secondary.
3. `FULL - SCALE`, secondary.

Apply Holm correction to the two secondary contrasts. Use TOST with a 90% interval and $\pm872$ ppm equivalence margin.

The primary estimator is a crossed hierarchical bootstrap with 10,000 replicates: resample the 75 master-seed blocks and 115 ID group blocks, retaining all arms and all `s` siblings. A mixed model with arm and region fixed effects and seed/group random intercepts is sensitivity analysis. For the eight-method comparison, average stochastic runs within group, use a blocked Friedman test, and Holm-adjust paired `FULL` comparisons against DEF, MAXP, MAXPW, and MINW.

## 10. Advisor-facing presentation

The main ID graph has eight fixed-order bars:

`BASE, CAP, SCALE, FULL, DEF, MAXP, MAXPW, MINW`.

Bar height is mean residual gap in ppm. Error lines are 95% crossed hierarchical bootstrap intervals for GEP and 95% group-bootstrap intervals for deterministic baselines. The caption states 345 instances, 115 groups, 75 GEP seeds, the 65,536-request budget, and the interval definition.

Companion outputs cover ID/OOD regions, run distributions, anytime performance, `FULL-MAXPW` paired effects, exactness/tail risk, row-order robustness, Pisinger transfer, representative expressions, and all 75 expressions per arm. The notebook uses `$...$` and `$$...$$` for mathematics.

Representative expressions are selected without test outcomes. Within each arm, retain final models no worse than one train-plus-validation group-level standard error above the best development mean; choose shortest ORF, lexicographically smallest simplified expression, then lowest seed index.

## 11. Lock and incident rules

The split, development folds, seeds, selected setup, code hashes, analysis code, contrast family, figure specification, and expression rule enter `protocol_lock.json` before test evaluation. Test commands refuse mismatched hashes.

If a genuine implementation bug is discovered after lock, record it in `protocol/amendments.md`, repair it, and rerun every affected arm. Negative, null, recovery-only, and domain-limited findings remain in the results.

## 12. Required artifacts

- `protocol_lock.json`, history hashes, environment record, and amendments;
- split, folds, seeds, power plan, and Pisinger manifests;
- complete irace and survivor traces;
- per-run atomic results plus merged models, histories, evaluations, expressions, and statistics CSVs;
- figure-source CSVs and publication PDF/SVG/PNG files;
- an executable advisor notebook and one-command analysis regeneration.

## 13. Methodological sources

1. Jooken, Leyman, and De Causmaecker, “A new class of hard problem instances for the 0-1 knapsack problem,” *EJOR*, 2022: https://www.sciencedirect.com/science/article/pii/S037722172101016X
2. López-Ibáñez et al., “The irace package,” *Operations Research Perspectives*, 2016: https://mlopez-ibanez.github.io/irace/
3. Pisinger, “Where are the hard knapsack problems?”, *Computers & Operations Research*, 2005: https://doi.org/10.1016/j.cor.2004.03.002
4. Demšar, “Statistical comparisons of classifiers over multiple data sets,” *JMLR*, 2006: https://jmlr.org/papers/v7/demsar06a.html
5. Beiranvand, Hare, and Lucet, “Best practices for comparing optimization algorithms”: https://arxiv.org/abs/1709.08242
6. López-Ibáñez, Branke, and Paquete, “Reproducibility in Evolutionary Computation,” *TELO*, 2021: https://doi.org/10.1145/3466624

# V3 verification report

## Scientific and implementation checks

- 29 original plus new tests pass in the independent V3 workspace. The staged public repository, including its additional existing packaging tests, passes all 45 tests.
- Tests cover the three feature definitions, correlation extremes and undefined correlation, zero-variance features, positive scaling and row-order invariance of features, deterministic label ties, actual R nearest-neighbor behavior and seeded class-vote ties, development/test instance and sibling separation, feasibility, certified-optimum bounds, and complete-group bootstrap resampling.
- All 50 original scientific lock entries verify through the local provenance adapter. The original lock remains byte-identical. All 20 published reference result tables are byte-identical.
- Inherited artifact checks verify 1,138 committed run directories, 675 models, 3,900 checkpoints, 12 hashed evaluation files, 31,800 Pisinger certificates, and the historical executed notebook. These are verification reads; the original analyses are unchanged.
- The revision freeze was written before test evaluation and records the source, protocol, inputs, development labels/features, runtime, and exact four genes. Its SHA-256 is `0b9a30612ae8b4f99a0fed887584c478340c367a2e0b4a3b55289a1d2c51475c`.
- Coverage is exactly 1,383 development and 1,594 test instances (345 ID and 1,249 OOD), with no development/test sibling overlap. There are exactly 14,346 test outcomes for nine methods. All are feasible, bounded by certified optima, and checked against selected-item sums.
- The four formulae and four fixed rules replay all 12,752 original method-instance outcomes with identical integer profits, weights, and optima. The maximum floating-point gap serialization difference is below 1e-7 ppm.
- A second fresh R process reproduces every kNN prediction. The four ID contrasts use all 115 complete sibling groups, 10,000 shared bootstrap draws, and the frozen adjusted endpoints.
- Runtime metadata distinguishes feature loading, R prediction, decoding, bootstrap, and replay. It is descriptive, not a speed comparison.

## V2 and runtime isolation

The copy audit verifies independent files, not hard links. All new entry-point outputs resolve inside V3 or an explicitly separate temporary build directory. The legacy Makefile is archived and no legacy tuning/training command was executed. A final read-only SHA-256 audit compares all 7,132 V2 files with the pre-copy fingerprint inventory; see `v2-immutability.log` and `provenance/v2_fingerprints_after_verification.json`.

The new environment uses the exact pinned package versions. PyPI was inaccessible, so independently copied installed distributions supplied the fresh V3 environment; `pip check` reports no broken requirements. Python 3.14.7, R 4.6.1, class 7.3-23, and Tectonic 0.17.0 are recorded. Kernel executables, caches, and runtime directories are V3-local. The original environment record remains unchanged.

## Submission and source checks

The inspected PDF is **five US Letter pages (612 × 792 points)**, including references, with the supplied IEEE conference class and original layout. All 24 font entries are embedded, subsetted, and Unicode-mapped; there are no Type 3 fonts. All five rendered pages were visually inspected for figure/table readability, clipping, collisions, margins, and reference layout.

The title, authors, abstract, keywords, and section structure are unchanged. Sections II-A–II-C and III-B–III-C are byte-identical. Tables I, II, III, and V are byte-identical; Table IV adds the selected model identifiers, mean gaps, MAXPW, and kNN. All three figure PDFs and IEEEtran.cls are byte-identical to the historical upload. Bibliography entries are in first-citation order, with 13 unique entries and no unresolved references or citations.

No overfull boxes occur. Remaining warnings are three underfull horizontal boxes (keywords and the final bibliography entry) and the original XeTeX TU/ptm initialization warnings. Visual review and the final embedded-font inventory found no resulting defect. The body uses embedded Nimbus Roman; figure fonts are embedded Times New Roman. No font size, margin, figure scale, or table spacing was reduced to force the page count.

A temporary copy containing only the submission folder rebuilt independently with local relative assets. Its five rendered pages are pixel-identical to the inspected final PDF. PDF metadata timestamps may differ; render identity establishes content/layout identity. The original final file was not overwritten by the independent build.

Final inspected `VA280.pdf` SHA-256: `8b74af2b5f232866677c37e6c4a80ce097e851531de396a2c8ce294fb1b3e8c9`.

The [conference submission page](https://www.iscmi.us/submission.html), checked on 2026-10-21, states that regular registration includes five pages and that page counts include figures, tables, and references. These are **local compliance checks**, not official IEEE certification. No organizer-provided PDF validation process was supplied or run.

## Public repository package

The update adds the revised paper, separate comparison package, compact results, and reproduction documentation to the existing public repository. Its original packaging adaptations and `artifacts-v1` release are preserved. Citation links provide access to the four reference articles; their PDFs are not distributed here. The [change record](../../docs/revision_changes.md) describes the differences from the original uploaded version.

The public Git whitespace check reports inherited whitespace in the byte-preserved IEEE class, design snapshot, manuscript lines, frozen R session output, and the unified diff. These artifacts were not normalized, to preserve their bytes. The new comparison code, shell entry points, and authored documentation pass the focused whitespace check.

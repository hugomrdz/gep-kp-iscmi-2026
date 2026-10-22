# Cleanup and preservation

The copy and runtime cleanup below took place in the author's local V3 workspace. The public package retains the existing standalone repository layout and records that preparation here.

- V2 was fingerprinted before an independent copy: 7,132 files, 2,098,785,851 bytes; every copied hash matched, with no symlinks or shared file inodes. The final V2 audit is recorded separately.
- Only `additionalArticles/ApproxCO_2011.pdf` was removed from the article collection. The other four PDFs remain in V3; public packaging contains citation links only.
- Copied Python/Numba caches, pytest cache, old Jupyter installation, IPython/Jupyter runtime configuration, Matplotlib cache, and old temporary PDF inspection files were removed and replaced with local V3 runtime state. Exact paths are in `provenance/cleanup.json`.
- The local V3 copy archives its original README, Makefile, and figure builder under its own `provenance/original/`. The public repository keeps its existing packaging adaptations and source snapshots. The added V3 entry point exposes the additional comparison, tests, kernel setup, and submission build.
- The copied figure builder's input/output roots now resolve inside V3. It is not used to replace the three preserved submitted figure assets.
- The parent experimental-design document is snapshotted in `provenance/experiment_design_iscmi_v2.md` and mapped to its original lock entry.
- Original scientific source, original lock, selected genes, results, historical `_v2` identifiers, and the original uploaded submission remain intact.
- `iscmi2026_submission_HugoMoreno/` contains exactly seven deliverables: the manuscript, supplied class, three figures, final `VA280.pdf`, and `build.sh`. Compilation files are written to an external temporary directory; review logs stay outside the submission folder.
- The public package preserves the existing packaging adaptations, original published PDF, Git history, and `artifacts-v1` release tag. No third-party article PDFs, notification/registration files, Python environment, cache, or bulk benchmark artifact is added to Git.

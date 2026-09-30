# Frozen input data and raw evaluations

The repository keeps the source, trained models, checkpoints, run records,
tuning evidence, and compact result tables in Git. Two uncompressed tar bundles
contain the frozen benchmark inputs and bulk evaluation records; their members
are already compressed. This keeps oversized files out of ordinary Git history.

The bundles are published in the [artifacts-v1 release](https://github.com/hugomrdz/gep-kp-iscmi-2026/releases/tag/artifacts-v1)
and cached locally in `release-assets/`. The URLs in
[`artifacts/manifest.json`](../artifacts/manifest.json) point to:

- `https://github.com/hugomrdz/gep-kp-iscmi-2026/releases/download/artifacts-v1/data.tar`
- `https://github.com/hugomrdz/gep-kp-iscmi-2026/releases/download/artifacts-v1/results.tar`

`data.tar` contains the Jooken ZIP and three Pisinger archives. `results.tar`
contains the original-order Jooken evaluations, ten row-order permutation
evaluations, and frozen Pisinger evaluations. The manifest records the exact
byte count and SHA-256 of both bundles and all 16 members. The original source
files remain available in the prepared local repository.

## Restore and verify

The helper uses only the Python standard library. Commands work from any
working directory when the script is addressed by its path. From the repository:

```sh
python3 scripts/artifacts.py fetch
python3 scripts/artifacts.py verify
```

Fetch can select `data` or `results`. Once a verified local bundle exists in
`release-assets/`, fetch reuses it. To restore bundles supplied offline, use:

```sh
python3 scripts/artifacts.py fetch --source-dir /path/to/bundles
```

Fetch first verifies the bundle fingerprint, then stages and verifies every
member before replacing any destination. Each replacement is an atomic rename.
The extractor rejects absolute paths, traversal, links, duplicate members, and
unlisted members. It does not extract through existing destination symlinks.
`verify` checks restored members and any cached bundle against the frozen
manifest; it does not contact the network. A download failure reports retry and offline-restoration options.

## Rebuild the release assets

With the complete original artifact files present:

```sh
python3 scripts/artifacts.py pack
```

Tar entry order, ownership, permissions, and timestamps are fixed. Repacking
must reproduce the manifest's fingerprints; the helper refuses to replace those
fingerprints with different scientific data. For future artifact versions, publish both `.tar`
files under a new release tag and retain the original frozen release. The ordinary Git
repository intentionally excludes the bundles and their large extracted members.

## Benchmark provenance

The Jooken archive is the original 21,305,404-byte GitHub archive used by the
ISCMI experiment. Its ZIP comment identifies commit
`df45dfade087aa3aa4ec8665e157efe362d20df7` in
[`JorikJooken/knapsackProblemInstances`](https://github.com/JorikJooken/knapsackProblemInstances).
It has SHA-256
`68ef9b6be17fbc37f303a250aa79cacfcbe7167d5f0b83f8f96c60d666f0fb26`
and preserves its original `knapsackProblemInstances-master/` directory. A fresh
commit-specific ZIP can have a different directory prefix and archive hash;
the release bundle preserves the exact experimental input.

The upstream README asks users to cite Jooken, Leyman, and De Causmaecker,
“A new class of hard problem instances for the 0–1 knapsack problem,”
*European Journal of Operational Research* 301(3), 841–854 (2022). It contains
no explicit license file. Pisinger's original source URLs, sizes, hashes, and
certificate audit are recorded in
[`protocol/pisinger_sources.md`](../protocol/pisinger_sources.md).
These third-party inputs retain their provenance; this package does not assign
a new license to them.

The benchmark archives total about 515 MiB. Bulk evaluation records total about
1.41 GiB and contain 41,503,185 evaluation rows. Full statistical reanalysis
requires the `results` group. Rebuilding the publication figures from their
saved compact tables does not require either bundle.

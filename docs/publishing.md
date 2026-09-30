# Publishing the prepared repository

This is a local publication package. No GitHub repository or release was created during preparation. The intended remote is:

```text
https://github.com/hugomrdz/gep-kp-iscmi-2026
```

The ordinary Git tree contains source, tests, protocol evidence, compact results, models/run records, notebook, figures, citation metadata, and the MIT license. The large benchmark archives and raw evaluations are present locally but excluded from Git. Their ready-to-upload assets are:

- `release-assets/data.tar`
- `release-assets/results.tar`

Before publication, run `make test`, `make verify`, and `.venv/bin/python scripts/artifacts.py verify all`. The bundle/member checksums must match `artifacts/manifest.json`.

Create the empty public repository, push the prepared `main` branch, and publish **both** assets under release tag `artifacts-v1`. The fetch script uses exactly that tag and those filenames. For example, after reviewing the local content and ensuring an initial commit exists:

```bash
gh repo create hugomrdz/gep-kp-iscmi-2026 --public --description "Reproduction package for the ISCMI 2026 GEP knapsack paper"
git push -u origin main
gh release create artifacts-v1 release-assets/data.tar release-assets/results.tar \
  --repo hugomrdz/gep-kp-iscmi-2026 \
  --title "Frozen ISCMI 2026 reproduction artifacts" \
  --notes-file docs/release-notes.md
```

After the release is available, update the preparation-status sentence in the README and `publication_status` in `artifacts/manifest.json`. Do not change asset checksums or replace the frozen protocol approval. Test a fresh clone with `make setup`, `make fetch`, `make verify`, and `make reproduce` before sharing the repository link with readers.

`data.tar` holds third-party benchmark files and attribution remains with the original sources; this repository's MIT license is not a dataset relicensing. Consult the source terms before redistributing those assets.

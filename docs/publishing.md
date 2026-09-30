# Published repository and release maintenance

The public repository is <https://github.com/hugomrdz/gep-kp-iscmi-2026>.
Its frozen benchmark inputs and raw evaluations are available in the
[artifacts-v1 release](https://github.com/hugomrdz/gep-kp-iscmi-2026/releases/tag/artifacts-v1).

The Git tree contains source, tests, protocol evidence, compact results,
models/run records, notebook, figures, the final paper, citation metadata,
and the MIT license. The large benchmark archives and raw evaluations are
excluded from Git and supplied as two release assets:

- `data.tar`
- `results.tar`

The fetch script uses this exact tag and these filenames. It verifies bundle
and member SHA-256 fingerprints against `artifacts/manifest.json` before
installing the files. An offline copy can be restored using
`python3 scripts/artifacts.py fetch all --source-dir /path/to/release-assets`.

For code or documentation maintenance, commit the reviewed changes and push
`main`. Keep the original protocol approval, source snapshots, and artifact
fingerprints intact. A new scientific experiment or a changed dataset belongs
in a separate protocol and versioned release; do not replace the original
frozen artifacts silently.

Before publishing another artifact version, run the tests, complete artifact
verification, and the reproduction commands. Publish both bundles under the
new version's tag and test restoration from a fresh clone.

`data.tar` holds third-party benchmark files. Attribution and terms remain
with the original sources; the repository's MIT license applies to its
original software and documentation.

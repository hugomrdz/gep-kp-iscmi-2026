#!/usr/bin/env python3
"""Compare regenerated result tables with the exact published table bytes."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    reference = json.loads((ROOT / "provenance/analysis_reference.json").read_text())
    failures = []
    for relative, expected in reference.items():
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"missing {relative}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(f"different {relative}")
    if failures:
        raise SystemExit("Published-table comparison failed:\n" + "\n".join(failures))
    print(f"PASS: all {len(reference)} result files are byte-identical to the published snapshot.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Record packaging-only changes without rewriting the paper's protocol lock.

This is a release-maintainer command, not a prerequisite for reproduction.
It refuses changed experimental source and verifies each archived original.
"""

from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io_utils import atomic_json, sha256_file  # noqa: E402
from src.protocol import (  # noqa: E402
    PACKAGING_ADAPTATIONS,
    PROTOCOL_LOCK_PATH,
    PUBLICATION_MANIFEST,
    locked_source_hashes,
    original_publication_hashes,
    verify_publication_sources,
)


def main() -> None:
    lock = json.loads(PROTOCOL_LOCK_PATH.read_text(encoding="utf-8"))
    original = original_publication_hashes(lock)
    current = locked_source_hashes()
    if set(current) != set(original):
        raise SystemExit(
            "Cannot package a different locked source set: "
            f"missing={sorted(set(original) - set(current))}, "
            f"extra={sorted(set(current) - set(original))}"
        )
    changed = {name for name in current if current[name] != original[name]}
    unsupported = changed - set(PACKAGING_ADAPTATIONS)
    if unsupported:
        raise SystemExit(f"Experimental or undeclared source changes: {sorted(unsupported)}")
    adaptations = {}
    for name in sorted(changed):
        snapshot = f"provenance/original/{name}"
        path = ROOT / snapshot
        if not path.is_file() or sha256_file(path) != original[name]:
            raise SystemExit(f"Archived original missing or changed: {snapshot}")
        adaptations[name] = {
            "original_sha256": original[name],
            "packaged_sha256": current[name],
            "original_snapshot": snapshot,
            "reason": PACKAGING_ADAPTATIONS[name],
        }
    manifest = {
        "schema_version": 1,
        "original_protocol_lock_sha256": sha256_file(PROTOCOL_LOCK_PATH),
        "original_source_prefix": "iscmi2026_v2/",
        "expected_source_hashes": current,
        "adaptations": adaptations,
        "historical_v1_policy": (
            "The original history manifest is retained without external V1 files. "
            "This publication verifies its own artifacts and does not claim "
            "to recheck the historical experiment."
        ),
    }
    atomic_json(manifest, PUBLICATION_MANIFEST)
    verify_publication_sources()
    print(
        f"Verified {len(current)} original locked artifacts; "
        f"recorded {len(adaptations)} explicit packaging adaptations."
    )


if __name__ == "__main__":
    main()

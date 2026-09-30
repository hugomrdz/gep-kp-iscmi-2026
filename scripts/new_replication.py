#!/usr/bin/env python3
"""Create a separate workspace that recomputes the frozen final experiment."""

from pathlib import Path
import argparse
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="new, nonexistent directory")
    args = parser.parse_args()
    destination = args.destination.expanduser().resolve()
    if destination.exists() or destination.is_relative_to(ROOT):
        parser.error("Choose a nonexistent directory outside the source repository")

    from src.protocol import verify_lock
    from src.io_utils import sha256_file
    from src.config import JOOKEN_ARCHIVE, JOOKEN_ARCHIVE_SHA256

    verify_lock()
    if not JOOKEN_ARCHIVE.is_file() or sha256_file(JOOKEN_ARCHIVE) != JOOKEN_ARCHIVE_SHA256:
        parser.error("Fetch and verify the benchmark data before creating a replication")
    manifest = json.loads((ROOT / "provenance/publication_manifest.json").read_text())
    locked = set(manifest["expected_source_hashes"])
    destination.mkdir(parents=True)
    excluded = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "tmp", "jupyter", "release-assets", ".DS_Store"}
    for item in ROOT.iterdir():
        if item.name in excluded or item.name in {"results", "figures", "notebooks", "paper_figures"} or item.name in {"fig01.pdf", "fig02.pdf", "fig03.pdf"}:
            continue
        if item.is_dir():
            shutil.copytree(item, destination / item.name, ignore=shutil.ignore_patterns(*excluded, "*.pyc", "*.nbi", "*.nbc"))
        elif item.is_file():
            shutil.copy2(item, destination / item.name)
    # Preserve only the locked development inputs and transfer manifest.
    # No completed final run or evaluation is copied, so resume cannot reuse it.
    names = {name for name in locked if name.startswith("results/")}
    names.add("results/pisinger_manifest_v2.csv")
    for name in sorted(names):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    print(f"Created independent final-experiment workspace: {destination}")
    print("Run make setup, make confirmatory, make analyze, make notebook, make paper-figures, then make verify.")
    print("Training starts from the frozen seeds and selected configuration; no final runs were copied.")


if __name__ == "__main__":
    main()

"""Verify the original scientific lock through explicit local path mappings."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def local_path(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Path escapes this package: {relative}")
    return path


def verify_inherited():
    mapping = json.loads(local_path("provenance/v3_original_lock_map.json").read_text())
    lock_path = local_path("protocol/protocol_lock.json")
    assert sha256(lock_path) == mapping["original_lock_sha256"]
    lock = json.loads(lock_path.read_text())
    assert lock["status"] == "locked"
    assert set(mapping["paths"]) == set(lock["source_hashes"])
    for original, expected in lock["source_hashes"].items():
        assert sha256(local_path(mapping["paths"][original])) == expected, original
    for name, expected in lock["pisinger_archives"].items():
        assert sha256(local_path(f"data/pisinger/{name}")) == expected, name
    assert sha256(local_path("results/pisinger_manifest_v2.csv")) == lock["pisinger_manifest_sha256"]
    refs = json.loads(local_path("provenance/analysis_reference.json").read_text())
    for name, expected in refs.items():
        assert sha256(local_path(name)) == expected, name
    return {"locked_sources": len(mapping["paths"]), "reference_results": len(refs),
            "original_lock_sha256": sha256(lock_path)}


def verify_v2(source):
    """Read-only audit of V2, used only in the author workspace."""
    source = Path(source).resolve()
    before = json.loads(local_path("provenance/v2_fingerprints_before.json").read_text())["files"]
    current = {str(p.relative_to(source)): p for p in source.rglob("*") if p.is_file()}
    assert set(current) == set(before), "V2 file inventory changed"
    for relative, p in current.items():
        assert not p.is_symlink()
        assert p.stat().st_size == before[relative]["size"], relative
        assert sha256(p) == before[relative]["sha256"], relative
    return {"files": len(current), "all_v2_fingerprints_unchanged": True}

"""The release must detect damaged artifacts without external historical files."""

from pathlib import Path
import json
import shutil

import pytest

from src import protocol
from src.io_utils import sha256_file


@pytest.fixture
def isolated_publication(tmp_path: Path, monkeypatch) -> Path:
    source = protocol.PROJECT_ROOT
    manifest = json.loads(protocol.PUBLICATION_MANIFEST.read_text(encoding="utf-8"))
    names = set(manifest["expected_source_hashes"])
    names.update(
        adaptation["original_snapshot"]
        for adaptation in manifest["adaptations"].values()
    )
    names.update({"protocol/protocol_lock.json", "provenance/publication_manifest.json"})
    for name in names:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, destination)
    for name, value in list(vars(protocol).items()):
        if isinstance(value, Path) and value.is_relative_to(source):
            monkeypatch.setattr(protocol, name, tmp_path / value.relative_to(source))
    return tmp_path


def test_publication_is_self_contained(isolated_publication: Path) -> None:
    messages = protocol.verify_history()
    assert any("locked artifacts" in message for message in messages)
    assert any("not distributed or rechecked" in message for message in messages)
    assert not (isolated_publication.parent / "iscmi2026").exists()


@pytest.mark.parametrize("mutation", ["changed", "missing", "extra"])
def test_locked_sources_detect_tampering(
    isolated_publication: Path, mutation: str
) -> None:
    target = isolated_publication / "src" / "gep.py"
    if mutation == "changed":
        target.write_text(target.read_text() + "\n# tampered\n")
    elif mutation == "missing":
        target.unlink()
    else:
        (isolated_publication / "src" / "unexpected.py").write_text("# extra\n")
    with pytest.raises(PermissionError, match="Publication source hash mismatch"):
        protocol.verify_publication_sources()


@pytest.mark.parametrize("mutation", ["changed", "missing"])
def test_archived_original_is_required(
    isolated_publication: Path, mutation: str
) -> None:
    target = isolated_publication / "provenance" / "original" / "src" / "config.py"
    if mutation == "changed":
        target.write_text("# corrupted original\n")
    else:
        target.unlink()
    with pytest.raises(PermissionError, match="Archived original changed or is missing"):
        protocol.verify_publication_sources()


def test_original_lock_cannot_change(isolated_publication: Path) -> None:
    lock = protocol.PROTOCOL_LOCK_PATH
    lock.write_text(lock.read_text() + "\n")
    with pytest.raises(PermissionError, match="Original protocol lock changed"):
        protocol.verify_publication_sources()


def test_published_lock_cannot_be_replaced(isolated_publication: Path) -> None:
    before = sha256_file(protocol.PROTOCOL_LOCK_PATH)
    with pytest.raises(PermissionError, match="preserves the original protocol lock"):
        protocol.create_lock("new-approver")
    assert sha256_file(protocol.PROTOCOL_LOCK_PATH) == before


def test_missing_publication_manifest_fails(isolated_publication: Path) -> None:
    protocol.PUBLICATION_MANIFEST.unlink()
    with pytest.raises(PermissionError, match="Missing publication manifest"):
        protocol.verify_history()


def test_manifest_cannot_omit_a_locked_source(isolated_publication: Path) -> None:
    manifest = json.loads(protocol.PUBLICATION_MANIFEST.read_text())
    del manifest["expected_source_hashes"]["src/gep.py"]
    protocol.PUBLICATION_MANIFEST.write_text(json.dumps(manifest))
    with pytest.raises(PermissionError, match="source set differs"):
        protocol.verify_publication_sources()


def test_algorithm_change_cannot_be_a_packaging_adaptation(
    isolated_publication: Path,
) -> None:
    target = isolated_publication / "src" / "gep.py"
    target.write_text(target.read_text() + "\n# experimental change\n")
    manifest = json.loads(protocol.PUBLICATION_MANIFEST.read_text())
    manifest["expected_source_hashes"]["src/gep.py"] = sha256_file(target)
    manifest["adaptations"]["src/gep.py"] = {"reason": "Not a packaging change"}
    protocol.PUBLICATION_MANIFEST.write_text(json.dumps(manifest))
    with pytest.raises(PermissionError, match="unsupported publication source adaptation"):
        protocol.verify_publication_sources()

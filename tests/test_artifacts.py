"""Safety checks for the public artifact downloader using tiny local bundles."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import tarfile

import pytest


@pytest.fixture
def artifacts(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "artifacts.py"
    spec = importlib.util.spec_from_file_location("artifact_helper", script)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.ROOT = tmp_path
    helper.MANIFEST = tmp_path / "artifacts" / "manifest.json"
    helper.BUNDLES = tmp_path / "release-assets"
    helper.GROUP_MEMBERS = {
        "data": ["data/first.zip", "data/second.tgz"],
        "results": ["results/raw.csv.gz"],
    }
    originals = {
        "data/first.zip": b"first input" * 7,
        "data/second.tgz": b"second input" * 9,
        "results/raw.csv.gz": b"evaluation rows" * 11,
    }
    for relative, content in originals.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    helper.pack(["data", "results"])
    return helper, originals


def add_regular(archive, name, content):
    member = tarfile.TarInfo(name)
    member.size = len(content)
    archive.addfile(member, io.BytesIO(content))


def test_verified_offline_restoration(artifacts, monkeypatch, tmp_path):
    helper, originals = artifacts
    offline = tmp_path / "offline"
    helper.BUNDLES.rename(offline)
    for relative in originals:
        (tmp_path / relative).write_bytes(b"old local content")
    monkeypatch.chdir(tmp_path.parent)

    helper.fetch(["data", "results"], offline)
    helper.verify(["data", "results"])

    for relative, content in originals.items():
        assert (tmp_path / relative).read_bytes() == content
    assert (helper.BUNDLES / "data.tar").is_file()
    assert (helper.BUNDLES / "results.tar").is_file()


def test_late_corruption_preserves_all_existing_destinations(artifacts, tmp_path):
    helper, originals = artifacts
    entry = helper.load_manifest()["groups"]["data"]
    corrupt = tmp_path / "corrupt.tar"
    with tarfile.open(corrupt, "w") as archive:
        for relative in helper.GROUP_MEMBERS["data"]:
            content = originals[relative]
            if relative.endswith("second.tgz"):
                content = b"x" * len(content)
            add_regular(archive, relative, content)
    # Let the outer bundle check pass to exercise a late member-hash failure.
    corrupt_entry = {**entry, **helper.fingerprint(corrupt)}
    for relative in originals:
        (tmp_path / relative).write_bytes(b"existing destination")
    before = {relative: (tmp_path / relative).read_bytes() for relative in originals}

    with pytest.raises(ValueError, match="SHA-256 differs"):
        helper.restore_bundle(corrupt, corrupt_entry)

    assert {relative: (tmp_path / relative).read_bytes() for relative in originals} == before


@pytest.mark.parametrize("kind", ["traversal", "symlink", "hardlink"])
def test_rejects_unsafe_archive_members(artifacts, tmp_path, kind):
    helper, originals = artifacts
    entry = helper.load_manifest()["groups"]["data"]
    unsafe = tmp_path / "unsafe.tar"
    with tarfile.open(unsafe, "w") as archive:
        if kind == "traversal":
            add_regular(archive, "../escaped.txt", b"escape")
        else:
            member = tarfile.TarInfo("data/first.zip")
            member.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
            member.linkname = "../escaped.txt"
            archive.addfile(member)
    unsafe_entry = {**entry, **helper.fingerprint(unsafe)}

    with pytest.raises(ValueError, match="Unsafe artifact path|not a regular file"):
        helper.restore_bundle(unsafe, unsafe_entry)

    assert not (tmp_path / "escaped.txt").exists()
    assert not (tmp_path.parent / "escaped.txt").exists()
    for relative, content in originals.items():
        assert (tmp_path / relative).read_bytes() == content


def test_rejects_destination_symlink(artifacts, tmp_path):
    helper, originals = artifacts
    entry = helper.load_manifest()["groups"]["data"]
    destination = tmp_path / "data/first.zip"
    destination.unlink()
    destination.symlink_to(tmp_path / "results/raw.csv.gz")

    with pytest.raises(ValueError, match="symlink"):
        helper.restore_bundle(helper.BUNDLES / "data.tar", entry)

    assert destination.is_symlink()
    assert (tmp_path / "results/raw.csv.gz").read_bytes() == originals["results/raw.csv.gz"]

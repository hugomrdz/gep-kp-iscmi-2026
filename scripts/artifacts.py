#!/usr/bin/env python3
"""Pack, restore, and verify the frozen ISCMI data and raw evaluation artifacts.

Only Python's standard library is required. Paths are relative to this script's
repository, regardless of the caller's working directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "artifacts" / "manifest.json"
BUNDLES = ROOT / "release-assets"
REPOSITORY = "https://github.com/hugomrdz/gep-kp-iscmi-2026"
RELEASE_TAG = "artifacts-v1"
BASE_URL = f"{REPOSITORY}/releases/download/{RELEASE_TAG}"
CHUNK_SIZE = 4 * 1024 * 1024
GROUP_MEMBERS = {
    "data": [
        "data/knapsack.zip",
        "data/pisinger/hardinstances_pisinger.tgz",
        "data/pisinger/largecoeff_pisinger.tgz",
        "data/pisinger/smallcoeff_pisinger.tgz",
    ],
    "results": [
        "results/confirmatory/evaluations_jooken_v2.csv.gz",
        *[
            f"results/confirmatory/row_order/permutation_{index:02d}.csv.gz"
            for index in range(1, 11)
        ],
        "results/transfer/evaluations_pisinger_v2.csv.gz",
    ],
}


def fingerprint(path: Path) -> dict[str, int | str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(CHUNK_SIZE), b""):
            digest.update(block)
            size += len(block)
    return {"bytes": size, "sha256": digest.hexdigest()}


def check_file(path: Path, expected: dict) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Missing regular artifact file: {path}")
    if path.stat().st_size != expected["bytes"]:
        raise ValueError(f"Artifact byte count differs: {path}")
    if fingerprint(path)["sha256"] != expected["sha256"]:
        raise ValueError(f"Artifact SHA-256 differs: {path}")


def safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or "\\" in value
        or "\x00" in value
        or any(part in ("", ".", "..") for part in value.split("/"))
        or path.as_posix() != value
    ):
        raise ValueError(f"Unsafe artifact path: {value!r}")
    return value


def destination(relative: str) -> Path:
    path = ROOT / safe_relative(relative)
    current = ROOT
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Artifact path passes through a symlink: {current}")
    return path


def load_manifest() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported artifact manifest schema")
    if manifest.get("repository") != REPOSITORY or manifest.get("release_tag") != RELEASE_TAG:
        raise ValueError("Artifact repository or release tag differs")
    if set(manifest.get("groups", {})) != set(GROUP_MEMBERS):
        raise ValueError("Manifest must contain the data and results groups")
    for group, allowed in GROUP_MEMBERS.items():
        entry = manifest["groups"][group]
        filename = f"{group}.tar"
        if entry.get("filename") != filename or entry.get("url") != f"{BASE_URL}/{filename}":
            raise ValueError(f"Unexpected bundle location for {group}")
        members = entry.get("members", [])
        paths = [safe_relative(member["path"]) for member in members]
        if sorted(paths) != sorted(allowed):
            raise ValueError(f"Manifest member list differs for {group}")
        for item in [entry, *members]:
            if not isinstance(item.get("bytes"), int) or item["bytes"] < 0:
                raise ValueError(f"Invalid artifact byte count in {group}")
            if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
                raise ValueError(f"Invalid artifact SHA-256 in {group}")
    return manifest


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
    try:
        temporary.chmod(0o644)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def pack(groups: list[str]) -> None:
    BUNDLES.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest() if MANIFEST.exists() else {
        "schema_version": 1,
        "repository": REPOSITORY,
        "release_tag": RELEASE_TAG,
        "publication_status": "not_published",
        "groups": {},
    }
    if not MANIFEST.exists() and set(groups) != set(GROUP_MEMBERS):
        raise ValueError("The first pack must include all groups to create a complete manifest")
    for group in groups:
        filename = f"{group}.tar"
        members = []
        with tempfile.NamedTemporaryFile(dir=BUNDLES, suffix=".tar", delete=False) as output:
            temporary = Path(output.name)
        try:
            with tarfile.open(temporary, "w", format=tarfile.USTAR_FORMAT) as archive:
                for relative in GROUP_MEMBERS[group]:
                    source = destination(relative)
                    if not source.is_file():
                        raise ValueError(f"Cannot pack missing artifact: {source}")
                    member = {"path": relative, **fingerprint(source)}
                    info = tarfile.TarInfo(relative)
                    info.size = member["bytes"]
                    info.mode = 0o644
                    info.mtime = 0
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    with source.open("rb") as stream:
                        archive.addfile(info, stream)
                    members.append(member)
            entry = {
                "filename": filename,
                "url": f"{BASE_URL}/{filename}",
                **fingerprint(temporary),
                "members": members,
            }
            if MANIFEST.exists() and entry != manifest["groups"][group]:
                raise ValueError(
                    f"{group} differs from the frozen manifest; pack does not rewrite published-study fingerprints"
                )
            temporary.chmod(0o644)
            os.replace(temporary, BUNDLES / filename)
            manifest["groups"][group] = entry
            print(f"Packed {filename}: {entry['bytes']:,} bytes, {len(members)} files", flush=True)
        finally:
            temporary.unlink(missing_ok=True)
    atomic_json(MANIFEST, manifest)


def acquire_bundle(entry: dict, source_dir: Path | None) -> Path:
    BUNDLES.mkdir(parents=True, exist_ok=True)
    cached = BUNDLES / entry["filename"]
    if source_dir is None and cached.exists():
        check_file(cached, entry)
        return cached
    with tempfile.NamedTemporaryFile(dir=BUNDLES, suffix=".download", delete=False) as output:
        temporary = Path(output.name)
        try:
            if source_dir is not None:
                source = source_dir.resolve() / entry["filename"]
                if not source.is_file():
                    raise ValueError(f"Offline bundle is missing: {source}")
                with source.open("rb") as stream:
                    shutil.copyfileobj(stream, output, CHUNK_SIZE)
            else:
                try:
                    with urlopen(entry["url"], timeout=60) as stream:
                        shutil.copyfileobj(stream, output, CHUNK_SIZE)
                except (HTTPError, URLError, TimeoutError) as error:
                    raise ValueError(
                        f"Cannot download {entry['url']}: {error}. The prepared artifacts-v1 release may "
                        "not yet be published. Ask the authors for data.tar and results.tar, then run "
                        "fetch --source-dir /path/to/bundles, or publish the prepared release assets first."
                    ) from error
            output.flush()
            check_file(temporary, entry)
            temporary.chmod(0o644)
            os.replace(temporary, cached)
        finally:
            temporary.unlink(missing_ok=True)
    return cached


def restore_bundle(bundle: Path, entry: dict) -> int:
    """Validate the complete bundle and staged contents before replacing any file."""
    check_file(bundle, entry)
    expected = {member["path"]: member for member in entry["members"]}
    temporary_root = ROOT / "tmp"
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="artifact-restore-", dir=temporary_root) as temporary:
        stage = Path(temporary)
        seen = set()
        with tarfile.open(bundle, "r:") as archive:
            for member in archive:
                relative = safe_relative(member.name)
                if relative not in expected or relative in seen:
                    raise ValueError(f"Unexpected or duplicate archive member: {relative}")
                if not member.isfile() or member.issym() or member.islnk():
                    raise ValueError(f"Archive member is not a regular file: {relative}")
                if member.size != expected[relative]["bytes"]:
                    raise ValueError(f"Archive member byte count differs: {relative}")
                destination(relative)
                staged = stage / relative
                staged.parent.mkdir(parents=True, exist_ok=True)
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError(f"Cannot read archive member: {relative}")
                with stream, staged.open("wb") as output:
                    shutil.copyfileobj(stream, output, CHUNK_SIZE)
                check_file(staged, expected[relative])
                seen.add(relative)
        if seen != set(expected):
            raise ValueError(f"Archive is missing members: {sorted(set(expected) - seen)}")
        # All bytes have passed validation; each installation is an atomic rename.
        for relative in expected:
            target = destination(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            staged = stage / relative
            staged.chmod(0o644)
            os.replace(staged, target)
    return len(expected)


def fetch(groups: list[str], source_dir: Path | None) -> None:
    manifest = load_manifest()
    for group in groups:
        entry = manifest["groups"][group]
        bundle = acquire_bundle(entry, source_dir)
        count = restore_bundle(bundle, entry)
        print(f"Restored and verified {group}: {count} files", flush=True)


def verify(groups: list[str]) -> None:
    manifest = load_manifest()
    for group in groups:
        entry = manifest["groups"][group]
        for member in entry["members"]:
            check_file(destination(member["path"]), member)
        cached = BUNDLES / entry["filename"]
        if cached.exists():
            check_file(cached, entry)
        print(f"Verified {group}: {len(entry['members'])} files" + (" and local bundle" if cached.exists() else ""), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("pack", "fetch", "verify"))
    parser.add_argument("group", nargs="?", default="all", choices=("all", *GROUP_MEMBERS))
    parser.add_argument("--source-dir", type=Path, help="Read fetch bundles from this directory instead of GitHub")
    args = parser.parse_args()
    if args.source_dir is not None and args.command != "fetch":
        parser.error("--source-dir is only supported by fetch")
    groups = list(GROUP_MEMBERS) if args.group == "all" else [args.group]
    try:
        if args.command == "pack":
            pack(groups)
        elif args.command == "fetch":
            fetch(groups, args.source_dir)
        else:
            verify(groups)
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
        print(f"Artifact operation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

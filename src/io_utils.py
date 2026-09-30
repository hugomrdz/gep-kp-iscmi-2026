"""Atomic artifact I/O and cryptographic provenance helpers."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable
import hashlib
import gzip
import io
import json
import os
import tempfile

import pandas as pd


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    if is_dataclass(value):
        value = asdict(value)
    return json.dumps(
        value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"


def atomic_text(value: str, path: Path | str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(value: Any, path: Path | str) -> None:
    atomic_text(canonical_json(value), path)


def atomic_csv(frame: pd.DataFrame, path: Path | str) -> None:
    destination = Path(path)
    if destination.name.endswith(".csv.gz"):
        atomic_csv_stream((frame,), destination)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    suffix = ".csv"
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.", suffix=suffix, dir=destination.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        frame.to_csv(temporary, index=False, lineterminator="\n")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_csv_stream(frames: Iterable[pd.DataFrame], path: Path | str) -> int:
    """Write compatible frames to one deterministic gzip CSV without concatenating RAM."""

    destination = Path(path)
    if not destination.name.endswith(".csv.gz"):
        raise ValueError("Streamed CSV output must end in .csv.gz")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.", suffix=".csv.gz", dir=destination.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    count = 0
    columns: list[str] | None = None
    try:
        with temporary.open("wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0, compresslevel=6) as gz:
                with io.TextIOWrapper(gz, encoding="utf-8", newline="") as handle:
                    for frame in frames:
                        if frame.empty:
                            continue
                        current = list(frame.columns)
                        if columns is None:
                            columns = current
                        elif current != columns:
                            raise ValueError("Streamed CSV frames have different columns")
                        frame.to_csv(
                            handle,
                            index=False,
                            header=count == 0,
                            lineterminator="\n",
                        )
                        count += len(frame)
                    handle.flush()
        if columns is None:
            raise ValueError("No non-empty frames were supplied")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return count


def hash_paths(paths: Iterable[Path], *, relative_to: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for path in sorted(paths, key=lambda item: item.as_posix()):
        if path.is_file():
            rows[path.relative_to(relative_to).as_posix()] = sha256_file(path)
    return rows


def atomic_run_directory(final_dir: Path, files: dict[str, str | bytes]) -> None:
    """Commit a complete run directory with `_SUCCESS.json` written last."""

    final_dir.parent.mkdir(parents=True, exist_ok=True)
    if final_dir.exists():
        raise FileExistsError(f"Run directory already exists: {final_dir}")
    temporary = Path(tempfile.mkdtemp(prefix=f".{final_dir.name}.", dir=final_dir.parent))
    try:
        hashes: dict[str, str] = {}
        for name, value in files.items():
            target = temporary / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, bytes):
                target.write_bytes(value)
            else:
                target.write_text(value, encoding="utf-8")
            hashes[name] = sha256_file(target)
        (temporary / "_SUCCESS.json").write_text(canonical_json({"files": hashes}), encoding="utf-8")
        temporary.replace(final_dir)
    finally:
        if temporary.exists():
            for child in sorted(temporary.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            temporary.rmdir()


def validate_run_directory(path: Path | str) -> dict[str, str]:
    """Validate a committed run directory and return its declared file hashes."""

    directory = Path(path)
    success = directory / "_SUCCESS.json"
    if not directory.is_dir() or not success.is_file():
        raise FileNotFoundError(f"Incomplete run directory: {directory}")
    payload = json.loads(success.read_text(encoding="utf-8"))
    hashes = payload.get("files")
    if not isinstance(hashes, dict) or not hashes:
        raise AssertionError(f"Malformed run marker: {success}")
    actual_names = {
        child.relative_to(directory).as_posix()
        for child in directory.rglob("*")
        if child.is_file() and child.name != "_SUCCESS.json"
    }
    if actual_names != set(hashes):
        raise AssertionError(
            f"Run files differ from marker in {directory}: "
            f"declared={sorted(hashes)}, actual={sorted(actual_names)}"
        )
    for name, expected in hashes.items():
        if sha256_file(directory / name) != expected:
            raise AssertionError(f"Run file hash mismatch: {directory / name}")
    return {str(name): str(value) for name, value in hashes.items()}

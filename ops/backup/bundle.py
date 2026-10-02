#!/usr/bin/env python3
"""Strict handling of a decrypted backup bundle. Used by restore-drill.sh; never trusts the archive.

    bundle.py extract TAR DEST ARTIFACT_NAME   unpack an allowlisted set of regular files, then validate the manifest

The bundle is attacker-controlled until its signature has been verified (restore-drill.sh does that first), and this
module still assumes the worst: it never calls tar's own extraction (no path, link, or device handling to get
wrong), it writes only files it names itself, and it rejects anything outside the exact expected shape.
"""
import json
import os
import re
import sys
import tarfile
from datetime import datetime

REQUIRED = ("manifest.json", "science_bank.dump")
OPTIONAL = ("env",)
MAX_BYTES = int(os.environ.get("MAX_BUNDLE_BYTES", str(4 * 1024**3)))  # per member
MAX_TOTAL_BYTES = int(os.environ.get("MAX_BUNDLE_TOTAL_BYTES", str(8 * 1024**3)))  # all members together

TABLE_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
VERSION_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")
CREATED_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
ARTIFACT_NAME_RE = re.compile(r"^science-bank-(\d{8}T\d{6}Z)(-[a-z0-9-]+)?\.tar\.age$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
PRINTABLE_RE = re.compile(r"^[\x20-\x7e]{0,200}$")


class BundleError(Exception):
    pass


def extract(tar_path, dest):
    """Copy the allowed members out of the tar, by name, as plain 0600 files."""
    try:
        tf = tarfile.open(tar_path, "r:")
    except (tarfile.TarError, OSError) as exc:
        raise BundleError(f"not a readable tar archive: {exc}")
    with tf:
        members = tf.getmembers()
        names = [m.name for m in members]
        if len(names) != len(set(names)):
            raise BundleError("the archive has duplicate member names")
        for m in members:
            if m.name not in REQUIRED + OPTIONAL:
                raise BundleError(f"unexpected archive member: {m.name[:60]!r}")
            if not m.isreg():
                raise BundleError(f"archive member {m.name!r} is not a regular file")
            if m.size > MAX_BYTES:
                raise BundleError(f"archive member {m.name!r} is implausibly large ({m.size} bytes)")
        if sum(m.size for m in members) > MAX_TOTAL_BYTES:
            raise BundleError("the archive is implausibly large in total")
        missing = [n for n in REQUIRED if n not in names]
        if missing:
            raise BundleError("the archive is missing: " + ", ".join(missing))
        os.makedirs(dest, mode=0o700, exist_ok=True)
        for m in members:
            src = tf.extractfile(m)
            target = os.path.join(dest, m.name)  # the name is from the allowlist, so this cannot escape dest
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as out:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)


def validate_manifest(dest, artifact_name):
    """Check the manifest's shape strictly; nothing in it is used (in SQL or on a terminal) before this passes."""
    try:
        manifest = json.load(open(os.path.join(dest, "manifest.json")))
    except (ValueError, OSError) as exc:
        raise BundleError(f"manifest.json is not valid JSON: {exc}")
    if not isinstance(manifest, dict):
        raise BundleError("manifest.json is not an object")
    if manifest.get("format") != 1:
        raise BundleError("unsupported manifest format")
    created = manifest.get("created_at")
    if not isinstance(created, str) or not CREATED_RE.match(created):
        raise BundleError("manifest created_at is malformed")
    version = manifest.get("alembic_version")
    if not isinstance(version, str) or not VERSION_RE.match(version):
        raise BundleError("manifest alembic_version is malformed")
    tables = manifest.get("tables")
    if not isinstance(tables, dict) or not tables or len(tables) > 64:
        raise BundleError("manifest tables is malformed")
    for name, count in tables.items():
        if not TABLE_RE.match(name) or not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise BundleError(f"manifest table entry is malformed: {name[:40]!r}")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) - set(REQUIRED + OPTIONAL) - {"manifest.json"}:
        raise BundleError("manifest files is malformed")
    if "science_bank.dump" not in files:
        raise BundleError("manifest does not describe the dump")
    for name, meta in files.items():
        if not isinstance(meta, dict) or not SHA_RE.match(str(meta.get("sha256", ""))) or not isinstance(meta.get("bytes"), int):
            raise BundleError(f"manifest entry for {name!r} is malformed")
        if name not in os.listdir(dest):
            raise BundleError(f"manifest lists {name!r} but the archive does not contain it")
    for name in os.listdir(dest):
        if name != "manifest.json" and name not in files:
            raise BundleError(f"the archive contains {name!r} but the manifest does not list it")
    for key in ("label", "host", "git_commit"):
        if not isinstance(manifest.get(key, ""), str) or not PRINTABLE_RE.match(manifest.get(key, "")):
            raise BundleError(f"manifest {key} is malformed")

    # The signature covers the bundle's content, not the file name it was uploaded under. The name is therefore bound
    # inside the signed manifest and must match exactly: no skew, and the label counts. A genuine backup copied to any
    # other name (newer, older, relabelled) is refused.
    recorded = manifest.get("artifact_name")
    if not isinstance(recorded, str) or not ARTIFACT_NAME_RE.match(recorded):
        raise BundleError("manifest artifact_name is missing or malformed")
    if recorded != artifact_name:
        raise BundleError(f"this file is named {artifact_name[:80]!r} but the signed manifest says it is "
                          f"{recorded!r}; it may have been renamed")
    stamp = ARTIFACT_NAME_RE.match(recorded).group(1)
    if datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%dT%H:%M:%SZ") != created:
        raise BundleError("manifest created_at does not match the timestamp in its artifact name")
    if (manifest.get("label") or "") != (ARTIFACT_NAME_RE.match(recorded).group(2) or "").lstrip("-"):
        raise BundleError("manifest label does not match its artifact name")
    return manifest


def main(argv):
    if len(argv) == 5 and argv[1] == "extract":
        _, _, tar_path, dest, artifact_name = argv
        try:
            extract(tar_path, dest)
            validate_manifest(dest, artifact_name)
        except BundleError as exc:
            print(f"bundle rejected: {exc}")
            return 1
        print("bundle structure and manifest ok")
        return 0
    print(__doc__)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv))

#!/usr/bin/env python3
"""Release manifest: generate and validate SHA-256 manifests for release artifacts."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Limitations of symlink protection:
# This script uses Path.is_symlink() and Path.resolve() to reject symlinks and
# verify path containment. These checks are not immune to TOCTOU races: between
# the check and the subsequent open(), a file could theoretically be replaced
# by a symlink. In the CI environment (trusted runner, no concurrent local
# attackers) this is acceptable. For higher assurance, os.open() with O_NOFOLLOW
# could be used, but that adds complexity without practical benefit here.


def sha256_file(path):
    """Compute SHA-256 of a regular file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_artifact_path(path, base_dir):
    """Validate that path is a regular file inside base_dir, not a symlink.

    Rejects symlinks (including broken ones and those pointing outside),
    directories, and any path that resolves outside base_dir.

    Note: Path.is_symlink() and Path.resolve() are used here. These are not
    immune to TOCTOU races in adversarial environments, but are sufficient
    for the CI release context.
    """
    if path.is_symlink():
        raise ValueError(f"symlink not allowed: {path}")
    if not path.is_file():
        raise FileNotFoundError(str(path))
    resolved = path.resolve()
    base_resolved = base_dir.resolve()
    if not resolved.is_relative_to(base_resolved):
        raise ValueError(f"path escapes artifacts directory: {path}")
    return resolved


def resolve_commit(tag):
    out = subprocess.check_output(
        ["git", "rev-parse", f"{tag}^{{commit}}"], text=True
    ).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", out):
        raise ValueError("bad commit")
    return out


def validate_manifest(manifest, artifact_paths=None, base_dir=None):
    """Validate a release manifest.

    If artifact_paths is provided, verifies that every artifact in the
    manifest exists in artifact_paths and its hash matches. If base_dir is
    provided, validates that all paths are safe (no symlinks, within base_dir)
    and that no extra files exist in the artifacts directory.
    """
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be object")
    if manifest.get("schema_version") != 1:
        raise ValueError("bad schema")
    if manifest.get("package") != "castlearq":
        raise ValueError("bad package")
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("bad version")
    tag = manifest.get("tag")
    if tag != f"v{version}":
        raise ValueError("tag mismatch")
    commit = manifest.get("commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("bad commit")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("bad artifacts")
    names = []
    for a in artifacts:
        if not isinstance(a, dict):
            raise ValueError("bad artifact")
        name = a.get("filename")
        digest = a.get("sha256")
        if not isinstance(name, str) or not name:
            raise ValueError("bad filename")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise ValueError(f"bad sha256 {name}")
        names.append(name)
    if len(set(names)) != len(names):
        raise ValueError("duplicate filenames")
    if artifact_paths is not None:
        if base_dir is not None:
            for p in artifact_paths:
                safe_artifact_path(p, base_dir)
        byname = {p.name: p for p in artifact_paths}
        for a in artifacts:
            p = byname.get(a["filename"])
            if p is None:
                raise ValueError(f"missing artifact {a['filename']}")
            if sha256_file(p) != a["sha256"]:
                raise ValueError(f"hash mismatch {a['filename']}")
        # Check for extra files (excluding SHA256SUMS)
        if base_dir is not None:
            manifest_names = {a["filename"] for a in artifacts}
            extra = [
                p for p in artifact_paths
                if p.name not in manifest_names and p.name != "SHA256SUMS"
            ]
            if extra:
                raise ValueError(
                    f"unexpected files in artifacts directory: "
                    f"{[p.name for p in extra]}"
                )
    return True


def build_manifest(package, version, tag, commit, artifact_paths):
    artifacts = []
    seen = set()
    for p in artifact_paths:
        if p.name in seen:
            raise ValueError("duplicate")
        seen.add(p.name)
        if p.is_symlink():
            raise ValueError(f"symlink not allowed: {p}")
        if not p.is_file():
            raise FileNotFoundError(str(p))
        artifacts.append({"filename": p.name, "sha256": sha256_file(p)})
    manifest = {
        "schema_version": 1,
        "package": package,
        "version": version,
        "tag": tag,
        "commit": commit,
        "artifacts": artifacts,
    }
    validate_manifest(manifest, artifact_paths)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--package", default="castlearq")
    g.add_argument("--version", required=True)
    g.add_argument("--tag", required=True)
    g.add_argument("--commit")
    g.add_argument("--artifacts-dir", required=True)
    g.add_argument("--patterns", nargs="+", default=["*.whl", "*.tar.gz"])
    g.add_argument("--manifest-out", required=True)
    g.add_argument("--sums-out", required=True)
    v = sub.add_parser("validate")
    v.add_argument("--manifest", required=True)
    v.add_argument("--artifacts-dir", required=True)
    v.add_argument("--sums-path", required=True)
    args = parser.parse_args()
    if args.cmd == "generate":
        if args.tag != f"v{args.version}":
            raise SystemExit("tag mismatch")
        commit = args.commit or resolve_commit(args.tag)
        adir = Path(args.artifacts_dir)
        files = []
        for pat in args.patterns:
            for p in sorted(adir.glob(pat)):
                safe_artifact_path(p, adir)
                files.append(p)
        if not files:
            raise SystemExit("no artifacts")
        manifest = build_manifest(args.package, args.version, args.tag, commit, files)
        Path(args.manifest_out).write_text(json.dumps(manifest, indent=2) + "\n")
        Path(args.sums_out).write_text(
            "".join(f"{a['sha256']}  {a['filename']}\n" for a in manifest["artifacts"])
        )
        print("generated")
    else:
        try:
            manifest = json.loads(Path(args.manifest).read_text())
        except (json.JSONDecodeError, OSError) as e:
            raise SystemExit(f"invalid manifest: {e}")
        adir = Path(args.artifacts_dir)
        files = []
        if adir.is_dir():
            for p in adir.iterdir():
                if p.is_symlink():
                    raise ValueError(f"symlink not allowed: {p}")
                if p.is_file():
                    files.append(p)
        validate_manifest(manifest, files, base_dir=adir)
        sums_path = Path(args.sums_path)
        if sums_path.is_symlink() or not sums_path.is_file():
            raise SystemExit(
                f"SHA256SUMS not found or not a regular file: {sums_path}"
            )
        expected = {}
        for line in sums_path.read_text().splitlines():
            if not line.strip():
                continue
            parts = line.split("  ", 1)
            if len(parts) != 2:
                raise SystemExit("malformed SHA256SUMS line")
            d, n = parts
            if not SHA256_RE.fullmatch(d):
                raise SystemExit(f"bad sha256 in sums: {d}")
            if not n:
                raise SystemExit("empty filename in sums")
            if n in expected:
                raise SystemExit(f"duplicate filename in sums: {n}")
            expected[n] = d
        actual = {a["filename"]: a["sha256"] for a in manifest["artifacts"]}
        if expected != actual:
            raise SystemExit("sums mismatch")
        print("valid")


if __name__ == "__main__":
    main()

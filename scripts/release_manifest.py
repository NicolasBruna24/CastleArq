#!/usr/bin/env python3
"""Release manifest: generate and validate SHA-256 manifests for release artifacts."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_sha256_sums(sums_path):
    """Read and strictly validate a SHA256SUMS file.

    Returns ``(expected, None)`` with ``expected = {filename: digest}`` on
    success, or ``(None, error_message)`` on any problem (missing file,
    malformed line, invalid digest, empty or duplicate filename).
    """
    sums_file = Path(sums_path)
    if not sums_file.is_file():
        return None, f"SHA256SUMS not found: {sums_path}"
    expected = {}
    try:
        lines = sums_file.read_text().splitlines()
    except OSError as exc:
        return None, f"Cannot read SHA256SUMS: {exc}"
    for line in lines:
        if not line.strip():
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            return None, f"malformed SHA256SUMS line: {line!r}"
        digest, name = parts
        if not SHA256_RE.fullmatch(digest):
            return None, f"bad sha256 in sums: {digest}"
        if not name:
            return None, "empty filename in sums"
        if name in expected:
            return None, f"duplicate filename in sums: {name}"
        expected[name] = digest.lower()
    return expected, None


def check_pypi_status(version, expected_files, sums_path):
    """Check PyPI status for a given version.

    Reads and validates expected hashes from sums_path.
    Returns a dict with:
    - 'status': 'not_published' (404), 'already_published' (exact match),
      'needs_publish' (200 but no match), or 'error'
    - 'published': dict of {filename: sha256} if available
    - 'error': error message if applicable
    """
    import json
    import urllib.request
    import urllib.error
    from pathlib import Path

    # Read and validate the sums manifest via the shared validator. No silent
    # substitution of expected_files by the names found in SHA256SUMS.
    expected, sums_error = load_sha256_sums(sums_path)
    if sums_error is not None:
        return {"status": "error", "published": {}, "error": sums_error}

    # The manifest must contain exactly the two names expected for the version;
    # abort on any discrepancy instead of normalizing silently.
    if set(expected.keys()) != expected_files:
        return {
            "status": "error",
            "published": {},
            "error": (
                f"SHA256SUMS filenames {sorted(expected.keys())} do not match "
                f"expected {sorted(expected_files)} for version {version}"
            ),
        }

    url = f"https://pypi.org/pypi/castlearq/{version}/json"

    try:
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"status": "not_published", "published": {}, "error": None}
        return {"status": "error", "published": {}, "error": f"HTTP {exc.code}"}
    except Exception as exc:
        return {"status": "error", "published": {}, "error": str(exc)}

    # The response must be a JSON object.
    if not isinstance(data, dict):
        return {"status": "error", "published": {}, "error": "response is not a JSON object"}

    # urls must be a list.
    if not isinstance(data.get("urls"), list):
        return {"status": "error", "published": {}, "error": "missing urls list"}

    published = {}
    seen = []
    for entry in data["urls"]:
        if not isinstance(entry, dict):
            return {"status": "error", "published": {}, "error": "invalid entry structure"}
        fname = entry.get("filename")
        digests = entry.get("digests")
        # filename must be a non-empty string.
        if not isinstance(fname, str) or fname == "":
            return {"status": "error", "published": {}, "error": "empty or invalid filename"}
        if not isinstance(digests, dict):
            return {"status": "error", "published": {}, "error": "invalid digests structure"}
        sha256 = digests.get("sha256")
        # sha256 must be exactly 64 hex characters.
        if not isinstance(sha256, str) or not SHA256_RE.fullmatch(sha256):
            return {"status": "error", "published": {}, "error": "missing or invalid sha256 digest"}
        # No duplicate filenames.
        if fname in seen:
            return {"status": "error", "published": {}, "error": f"duplicate filename {fname!r} in PyPI response"}
        seen.append(fname)
        published[fname] = sha256.lower()

    # The manifest must contain exactly the two names expected for the version.
    if set(published.keys()) != expected_files:
        return {
            "status": "needs_publish",
            "published": published,
            "error": (
                f"PyPI files {sorted(published.keys())} do not match "
                f"expected {sorted(expected_files)} for version {version}"
            ),
        }

    mismatches = []
    for f in expected_files:
        if published.get(f) != expected.get(f):
            mismatches.append(f"{f}: PyPI={published.get(f)}, expected={expected.get(f)}")
    if mismatches:
        return {
            "status": "needs_publish",
            "published": published,
            "error": f"hash mismatch: {'; '.join(mismatches)}",
        }

    return {
        "status": "already_published",
        "published": published,
        "error": None,
    }


def verify_artifact_hashes(artifact_path, expected_hash):
    """Verify a single artifact's SHA-256 hash."""
    import hashlib
    h = hashlib.sha256()
    with open(artifact_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    actual = h.hexdigest()
    return actual == expected_hash.lower()

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


def parse_markdown_manifest(path, version, tag, commit):
    """Parse a Markdown release manifest and return expected SHA-256 lines.

    Reads the candidate-artifacts section from a Markdown manifest produced
    for a release preparation (e.g. ``v{version}-manifest.md``) and returns a
    list of ``<digest>  dist/<filename>`` strings, one per expected artifact.
    """
    # --- Identity fields (Version / Tag / Commit) -------------------------
    text = Path(path).read_text(encoding="utf-8")
    # --- Candidate-artifacts section heading ------------------------------
    candidate_heading = "### New candidate artifacts (this preparation)"
    occurrences = text.count(candidate_heading)
    if occurrences == 0:
        raise ValueError(
            f"candidate artifacts section not found in {path}; "
            f"expected heading '{candidate_heading}'"
        )
    if occurrences > 1:
        raise ValueError(
            f"candidate artifacts section is ambiguous in {path}; "
            f"expected exactly one heading '{candidate_heading}'"
        )
    idx = text.find(candidate_heading)
    section = text[idx:]

    # --- Validación de identidad fuera de bloques de código ----------------
    # Buscar Version:, Tag: y Commit: fuera de cercas de código en todo el documento.
    _dentro_cerca = False
    _cerca_caracter = None
    _cerca_largo = 0
    _count_version = _count_tag = _count_commit = 0
    for _linea in text.splitlines():
        if _linea.startswith("```") or _linea.startswith("~~~"):
            if not _dentro_cerca:
                _dentro_cerca = True
                _cerca_caracter = _linea[:3]
                _cerca_largo = len(_linea) - len(_linea.lstrip(_cerca_caracter))
            else:
                if _linea.startswith(_cerca_caracter):
                    _largo_cierre = len(_linea) - len(_linea.lstrip(_cerca_caracter))
                    if _largo_cierre >= _cerca_largo:
                        _dentro_cerca = False
                        _cerca_caracter = None
            continue
        if _dentro_cerca:
            continue
        if _linea.startswith("Version:"):
            _count_version += 1
            _v = _linea[len("Version:"):].strip()
            if _v != version:
                raise ValueError(
                    f"manifest {path} Version={_v} does not match expected {version}"
                )
        elif _linea.startswith("Tag:"):
            _count_tag += 1
            _t = _linea[len("Tag:"):].strip()
            if _t != tag:
                raise ValueError(
                    f"manifest {path} Tag={_t} does not match expected {tag}"
                )
        elif _linea.startswith("Commit:"):
            _count_commit += 1
            _c = _linea[len("Commit:"):].strip()
            if _c != commit:
                raise ValueError(
                    f"manifest {path} Commit={_c} does not match expected {commit}"
                )

    if _count_version > 1:
        raise ValueError(f"manifest {path} has duplicate 'Version' fields")
    if _count_tag > 1:
        raise ValueError(f"manifest {path} has duplicate 'Tag' fields")
    if _count_commit > 1:
        raise ValueError(f"manifest {path} has duplicate 'Commit' fields")
    if _count_version == 0:
        raise ValueError(f"manifest {path} is missing 'Version' field")
    if _count_tag == 0:
        raise ValueError(f"manifest {path} is missing 'Tag' field")
    if _count_commit == 0:
        raise ValueError(f"manifest {path} is missing 'Commit' field")

    wheel = f"castlearq-{version}-py3-none-any.whl"
    sdist = f"castlearq-{version}.tar.gz"
    expected_names = {wheel, sdist}

    # --- Parser state ------------------------------------------------------
    dentro_cerca = False
    cerca_caracter = None
    cerca_largo_apertura = 0
    nombre_pendiente = None
    nombres_vistos = set()
    hashes_vistos = set()
    asignaciones = {}
    errores = []

    def rechazar(mensaje):
        errores.append(mensaje)

    for linea in section.splitlines():
        # --- Códigos de cerca (apertura o cierre) — se evalúan primero ---
        es_cerca_apertura = False
        caracter = None
        largo = 0

        if linea.startswith("```"):
            caracter = "`"
            largo = len(linea) - len(linea.lstrip("`"))
            if largo >= 3:
                es_cerca_apertura = True
        elif linea.startswith("~~~"):
            caracter = "~"
            largo = len(linea) - len(linea.lstrip("~"))
            if largo >= 3:
                es_cerca_apertura = True

        if dentro_cerca:
            if cerca_caracter is not None and linea.startswith(cerca_caracter):
                largo_cierre = len(linea) - len(linea.lstrip(cerca_caracter))
                if largo_cierre >= cerca_largo_apertura:
                    dentro_cerca = False
                    if nombre_pendiente is not None:
                        rechazar(
                            f"nombre '{nombre_pendiente}' sin hash al cerrar cerca"
                        )
                    nombre_pendiente = None
            continue

        if es_cerca_apertura:
            dentro_cerca = True
            cerca_caracter = caracter
            cerca_largo_apertura = largo
            continue

        # --- Fuera de cercas: contenido de la sección ---------------------
        if linea.strip() == "":
            continue

        if linea.startswith("SHA-256:"):
            if nombre_pendiente is None:
                rechazar("'SHA-256:' sin nombre de artefacto pendiente")
            else:
                hash_texto = linea[len("SHA-256:"):].strip()
                if not re.fullmatch(r"[0-9a-fA-F]{64}", hash_texto):
                    rechazar(f"hash mal formado: {hash_texto}")
                elif hash_texto.lower() in hashes_vistos:
                    rechazar(f"hash duplicado: {hash_texto}")
                elif nombre_pendiente not in expected_names:
                    rechazar(f"nombre inesperado: {nombre_pendiente}")
                elif nombre_pendiente in nombres_vistos:
                    rechazar(f"nombre duplicado: {nombre_pendiente}")
                elif nombre_pendiente in asignaciones:
                    rechazar(f"asignación duplicada para {nombre_pendiente}")
                else:
                    asignaciones[nombre_pendiente] = hash_texto.lower()
                    nombres_vistos.add(nombre_pendiente)
                    hashes_vistos.add(hash_texto.lower())
            nombre_pendiente = None
            continue

        match = re.match(r"^#{2,3}\s", linea)
        if match and linea.strip() != candidate_heading:
            if nombre_pendiente is not None:
                rechazar(f"nombre '{nombre_pendiente}' sin hash al cerrar sección")
            break

        candidato = linea.strip()
        if candidato in expected_names:
            if nombre_pendiente is not None:
                rechazar(
                    f"nombre '{nombre_pendiente}' sin hash antes de '{candidato}'"
                )
            nombre_pendiente = candidato

    # --- Fin del manifiesto (EOF) ------------------------------------------
    if dentro_cerca:
        rechazar("cerca de código sin cierre válido al finalizar el manifiesto")
    if nombre_pendiente is not None:
        rechazar(f"nombre '{nombre_pendiente}' sin hash al finalizar el manifiesto")

    if set(asignaciones.keys()) != expected_names:
        rechazar(f"se esperan exactamente los dos artefactos: {sorted(expected_names)}")

    if errores:
        raise ValueError("; ".join(errores))

    return [
        f"{asignaciones[wheel]}  {wheel}",
        f"{asignaciones[sdist]}  {sdist}",
    ]


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
    v.add_argument("--manifest", required=False)
    v.add_argument("--artifacts-dir", required=True)
    v.add_argument("--sums-path", required=True)
    p = sub.add_parser("parse-markdown")
    p.add_argument("--manifest", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--tag", required=True)
    p.add_argument("--commit", required=True)
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
    elif args.cmd == "parse-markdown":
        try:
            lines = parse_markdown_manifest(
                args.manifest, args.version, args.tag, args.commit
            )
        except ValueError as exc:
            raise SystemExit(str(exc))
        for line in lines:
            print(line)
    else:
        adir = Path(args.artifacts_dir)
        if not adir.is_dir():
            raise SystemExit(f"artifacts directory not found: {adir}")

        # Collect real files from dist/ (reject symlinks, directories, unsafe paths).
        files = []
        for p in sorted(adir.iterdir()):
            if p.is_symlink():
                raise ValueError(f"symlink not allowed: {p}")
            if p.is_dir():
                raise ValueError(f"unexpected directory in artifacts dir: {p}")
            if p.is_file():
                safe_artifact_path(p, adir)
                files.append(p)

        # Load expected hashes from SHA256SUMS via the shared validator.
        sums_path = Path(args.sums_path)
        if sums_path.is_symlink() or not sums_path.is_file():
            raise SystemExit(
                f"SHA256SUMS not found or not a regular file: {sums_path}"
            )
        expected, sums_error = load_sha256_sums(str(sums_path))
        if sums_error is not None:
            raise SystemExit(sums_error)

        # Build actual map from real files on disk.
        actual = {}
        for p in files:
            actual[p.name] = sha256_file(p)

        # The set of artifacts must match exactly.
        expected_set = set(expected.keys())
        actual_set = set(actual.keys())
        if expected_set != actual_set:
            missing = sorted(expected_set - actual_set)
            extra = sorted(actual_set - expected_set)
            parts = []
            if missing:
                parts.append(f"missing artifact(s): {', '.join(missing)}")
            if extra:
                parts.append(f"extra artifact(s): {', '.join(extra)}")
            raise SystemExit("; ".join(parts))

        # Every hash must match.
        for name, digest in expected.items():
            if actual[name] != digest:
                raise SystemExit(f"hash mismatch {name}")

        # Optional legacy path: when --manifest is provided, also cross-check
        # the manifest JSON against the same expected hashes.
        if args.manifest:
            manifest_path = Path(args.manifest)
            if manifest_path.is_symlink() or not manifest_path.is_file():
                raise SystemExit(
                    f"manifest not found or not a regular file: {manifest_path}"
                )
            try:
                manifest = json.loads(manifest_path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                raise SystemExit(f"invalid manifest: {e}")
            validate_manifest(manifest, files, base_dir=adir)
            actual_manifest = {
                a["filename"]: a["sha256"] for a in manifest["artifacts"]
            }
            if expected != actual_manifest:
                raise SystemExit("sums mismatch")

        print("valid")


if __name__ == "__main__":
    main()

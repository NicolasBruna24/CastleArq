# Copyright 2026 Nicolas Bruna
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""B9.81 tests: Hugging Face discovery provider (AC1-AC15)."""
from __future__ import annotations

import ast
import base64
import hashlib
import json
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError

from castlearq.discovery import (
    DiscoveredArtifact,
    DiscoveryError,
    ModelCandidate,
    ModelDiscovery,
    ModelVariant,
)
from castlearq.sources.base import ModelSource
from castlearq.sources.huggingface import HuggingFaceSource, SourceError
from castlearq.sources.huggingface_discovery import HuggingFaceDiscoveryProvider

MODULE_PATH = Path("castlearq/sources/huggingface_discovery.py")
DISCOVERY_PATH = Path("castlearq/discovery.py")
DISCOVERY_SHA256 = "bacc883c3d1d20e0fcbc41afe366a653a97815c3e3219849951f9668af5ba48c"

REPO = "owner/repository"  # not mapped in model_identity (AC7)
SHA = "0123456789abcdef0123456789abcdef01234567"
OID_Q4 = "aa" * 32
OID_Q8 = "bb" * 32


def _wire(value):
    if isinstance(value, Exception):
        return value
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return json.dumps(value).encode("utf-8")


def make_provider(routes):
    """Build a provider with a recording fake transport.

    ``routes`` is an ordered list of ``(url_substring, value)`` where value is
    a JSON-able object, raw bytes, an Exception to raise, or a
    ``(body, headers)`` tuple of those. Routing is by first match.
    """

    def respond(url):
        for key, value in routes:
            if key in url:
                if isinstance(value, Exception):
                    raise value
                if isinstance(value, tuple):
                    body, headers = value
                    return (_wire(body), headers)
                return _wire(value)
        raise AssertionError(f"unexpected url: {url}")

    calls: list[tuple[str, float]] = []

    def transport(url, timeout):
        calls.append((url, timeout))
        return respond(url)

    return HuggingFaceDiscoveryProvider(transport=transport), calls


def metadata_payload(**over):
    payload = {
        "id": REPO,
        "sha": SHA,
        "author": "owner",
        "tags": ["gguf"],
        "config": {"model_type": "llama"},
        "siblings": [{"rfilename": "model-Q4_K_M.gguf"}],
    }
    payload.update(over)
    return payload


def tree_payload():
    return [
        {"path": "model-Q8_0.gguf", "type": "file", "size": 5678,
         "lfs": {"oid": OID_Q8, "size": 5678}},
        {"path": "README.md", "type": "file", "size": 10},
        {"path": "model-Q4_K_M.gguf", "type": "file", "size": 1234,
         "lfs": {"oid": OID_Q4, "size": 1234}},
    ]


def q4_tree():
    return [
        {"path": "model-Q4_K_M.gguf", "type": "file", "size": 1234,
         "lfs": {"oid": OID_Q4, "size": 1234}},
    ]


def search_payload():
    return [
        {"id": REPO,
         "author": "owner",
         "tags": ["gguf", "text-generation"],
         "config": {"model_type": "llama"},
         "siblings": [{"rfilename": "model-Q4_K_M.gguf"},
                      {"rfilename": "README.md"}]},
        {"id": "owner/plain",
         "siblings": [{"rfilename": "README.md"}]},
        42,
        {"no": "id"},
    ]


def inspect_routes(**overrides):
    def wire(key, default):
        value = overrides.get(key, default)
        return value if isinstance(value, Exception) else _wire(value)

    return [
        ("/tree/", wire("tree", tree_payload())),
        (f"/models/{REPO}", wire("metadata", metadata_payload())),
    ]


def cursor_token(payload):
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def imported_modules():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


class ContractTests(unittest.TestCase):
    """AC1: provider exists, implements ModelDiscovery, is instantiable."""

    def test_provider_implements_port(self):
        self.assertTrue(issubclass(HuggingFaceDiscoveryProvider, ModelDiscovery))
        self.assertEqual(HuggingFaceDiscoveryProvider.__abstractmethods__, frozenset())
        provider = HuggingFaceDiscoveryProvider()
        self.assertTrue(callable(provider.search))
        self.assertTrue(callable(provider.inspect))

    def test_provider_is_frozen_dataclass(self):
        import dataclasses

        self.assertTrue(dataclasses.is_dataclass(HuggingFaceDiscoveryProvider))
        provider = HuggingFaceDiscoveryProvider()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            provider.timeout = 1.0  # type: ignore[misc]


class SearchTests(unittest.TestCase):
    """AC2: search returns candidates and an opaque cursor."""

    def test_search_returns_candidates(self):
        provider, calls = make_provider([("/api/", search_payload())])
        candidates, next_cursor = provider.search("llama", limit=5)
        self.assertIsInstance(candidates, tuple)
        self.assertIsNone(next_cursor)
        self.assertEqual(len(candidates), 2)
        first, second = candidates
        self.assertIsInstance(first, ModelCandidate)
        self.assertEqual(
            (first.provider_id, first.repository, first.author),
            ("huggingface", REPO, "owner"),
        )
        self.assertEqual(first.tags, ("gguf", "text-generation"))
        self.assertEqual(first.declared_architecture, "llama")
        self.assertTrue(first.has_gguf)
        self.assertIsNone(first.display_name)
        self.assertIsNone(first.description)
        self.assertEqual(second.repository, "owner/plain")
        self.assertFalse(second.has_gguf)
        self.assertIsNone(second.declared_architecture)
        self.assertEqual(calls[0][1], 10.0)

    def test_search_request_shape(self):
        provider, calls = make_provider([("/api/", b"[]")])
        provider.search("llama 7b", limit=7)
        url = calls[0][0]
        self.assertTrue(url.startswith("https://huggingface.co/api/models?"))
        self.assertIn("limit=7", url)
        self.assertIn("full=true", url)
        self.assertIn("search=llama%207b", url)

    def test_search_timeout_is_forwarded(self):
        provider, calls = make_provider([("/api/", b"[]")])
        provider = HuggingFaceDiscoveryProvider(
            transport=provider.transport, timeout=3.5
        )
        provider.search("x")
        self.assertEqual(calls[0][1], 3.5)

    def test_search_skips_malformed_entries(self):
        payload = [42, None, {}, {"no": "id"}, {"id": 7}, {"id": REPO}]
        provider, _ = make_provider([("/api/", payload)])
        candidates, _ = provider.search("x")
        self.assertEqual([c.repository for c in candidates], [REPO])

    def test_search_has_gguf_from_siblings(self):
        payload = [{"id": "owner/a", "siblings": [{"rfilename": "m.gguf"}]}]
        provider, _ = make_provider([("/api/", payload)])
        candidates, _ = provider.search("x")
        self.assertTrue(candidates[0].has_gguf)

    def test_search_has_gguf_from_tag(self):
        payload = [{"id": "owner/a", "tags": ["GGUF"]}]
        provider, _ = make_provider([("/api/", payload)])
        candidates, _ = provider.search("x")
        self.assertTrue(candidates[0].has_gguf)

    def test_search_has_gguf_false_when_undeterminable(self):
        payload = [
            {"id": "owner/a", "siblings": 42, "tags": "not-a-list"},
            {"id": "owner/b"},
        ]
        provider, _ = make_provider([("/api/", payload)])
        candidates, _ = provider.search("x")
        self.assertEqual(len(candidates), 2)
        for candidate in candidates:
            self.assertFalse(candidate.has_gguf)
            self.assertEqual(candidate.tags, ())

    def test_search_empty_result(self):
        provider, calls = make_provider([("/api/", [])])
        candidates, next_cursor = provider.search("")
        self.assertEqual(candidates, ())
        self.assertIsNone(next_cursor)
        self.assertNotIn("search=", calls[0][0])

    def test_search_missing_optional_metadata(self):
        provider, _ = make_provider([("/api/", [{"id": "owner/minimal"}])])
        candidates, _ = provider.search("x")
        (candidate,) = candidates
        self.assertIsNone(candidate.display_name)
        self.assertIsNone(candidate.author)
        self.assertIsNone(candidate.description)
        self.assertIsNone(candidate.declared_architecture)
        self.assertEqual(candidate.tags, ())

    def test_search_invalid_repository_entry_rejected(self):
        provider, _ = make_provider([("/api/", [{"id": "../evil"}])])
        with self.assertRaises(DiscoveryError):
            provider.search("x")

    def test_search_program_argument_validation(self):
        provider, calls = make_provider([("/api/", b"[]")])
        with self.assertRaises(TypeError):
            provider.search(123)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            provider.search("x", cursor=5)  # type: ignore[arg-type]
        for bad_limit in (0, -1, 1001, True, "5"):
            with self.assertRaises(ValueError):
                provider.search("x", limit=bad_limit)  # type: ignore[arg-type]
        self.assertEqual(calls, [])


class PaginationTests(unittest.TestCase):
    """AC2 / section 7: opaque cursor with strict validation."""

    def _page1_with_link(self):
        link = (
            "<https://huggingface.co/api/models?search=x&limit=1"
            "&cursor=ABC123>; rel=\"next\""
        )
        return ([{"id": REPO}], {"Link": link})

    def test_next_cursor_when_link_header_present(self):
        provider, _ = make_provider([("/api/", self._page1_with_link())])
        candidates, next_cursor = provider.search("x", limit=1)
        self.assertEqual(len(candidates), 1)
        self.assertIsInstance(next_cursor, str)
        self.assertNotIn("huggingface", next_cursor)
        self.assertNotIn("rel=", next_cursor)
        self.assertNotIn("<", next_cursor)

    def test_cursor_second_page_and_termination(self):
        page1 = self._page1_with_link()
        page2 = [{"id": "owner/second"}]
        provider, calls = make_provider([
            ("cursor=ABC123", page2),
            ("/api/models?", page1),
        ])
        _, next_cursor = provider.search("x", limit=1)
        self.assertIsNotNone(next_cursor)
        candidates, second_cursor = provider.search("x", limit=1, cursor=next_cursor)
        self.assertIsNone(second_cursor)
        self.assertEqual([c.repository for c in candidates], ["owner/second"])
        second_url = calls[1][0]
        self.assertTrue(second_url.startswith("https://huggingface.co/api/models?"))
        self.assertIn("cursor=ABC123", second_url)

    def test_no_next_cursor_without_link_header(self):
        provider, _ = make_provider([("/api/", ([{"id": REPO}], {}))])
        _, next_cursor = provider.search("x")
        self.assertIsNone(next_cursor)

    def test_link_header_without_next_relation(self):
        headers = {"Link": "<https://huggingface.co/api/models?cursor=1>; rel=\"prev\""}
        provider, _ = make_provider([("/api/", ([], headers))])
        _, next_cursor = provider.search("x")
        self.assertIsNone(next_cursor)

    def test_malformed_cursor_rejected(self):
        provider, calls = make_provider([("/api/", b"[]")])
        for bad in ("", "@@@@", cursor_token({"bad": 1}),
                    cursor_token({"v": 2, "p": "/api/models", "q": ""}),
                    cursor_token({"v": 1, "p": "/api/models"})):
            with self.assertRaises(DiscoveryError):
                provider.search("x", cursor=bad)
        self.assertEqual(calls, [])

    def test_cursor_cannot_leave_api_path(self):
        provider, calls = make_provider([("/api/", b"[]")])
        for path in ("/etc/passwd", "/api/../secret", "//evil", "/apix/models",
                     "/api/models?x=1", "/api/models#frag"):
            token = cursor_token({"v": 1, "p": path, "q": ""})
            with self.assertRaises(DiscoveryError):
                provider.search("x", cursor=token)
        self.assertEqual(calls, [])

    def test_cursor_cannot_introduce_host(self):
        provider, calls = make_provider([("/api/", b"[]")])
        token = cursor_token({"v": 1, "p": "/api/models",
                              "q": "next=https://evil.example/x"})
        with self.assertRaises(DiscoveryError):
            provider.search("x", cursor=token)
        token = cursor_token({"v": 1, "p": "/api/models", "q": "a=\x00b"})
        with self.assertRaises(DiscoveryError):
            provider.search("x", cursor=token)
        self.assertEqual(calls, [])

    def test_foreign_pagination_link_rejected(self):
        headers = {"Link": "<https://evil.example/api/models?cursor=1>; rel=\"next\""}
        provider, _ = make_provider([("/api/", ([], headers))])
        with self.assertRaises(DiscoveryError):
            provider.search("x")


class InspectTests(unittest.TestCase):
    """AC3 / AC5 / AC6 / section 10-13: variants, grouping and declared data."""

    def test_inspect_returns_variants(self):
        provider, calls = make_provider(inspect_routes())
        variants = provider.inspect(REPO)
        self.assertIsInstance(variants, tuple)
        self.assertEqual(len(variants), 2)
        for variant in variants:
            self.assertIsInstance(variant, ModelVariant)
            self.assertIsInstance(variant.candidate, ModelCandidate)
            self.assertEqual(variant.candidate.repository, REPO)
            self.assertEqual(variant.candidate.provider_id, "huggingface")
            self.assertTrue(variant.candidate.has_gguf)
            self.assertEqual(variant.candidate.author, "owner")
            self.assertEqual(variant.candidate.declared_architecture, "llama")
        self.assertEqual(
            [v.declared_quantization for v in variants], ["Q4_K_M", "Q8_0"]
        )
        self.assertEqual(len(calls), 2)

    def test_declared_metadata_fields(self):
        provider, _ = make_provider(inspect_routes(tree=q4_tree()))
        (variant,) = provider.inspect(REPO)
        artifact = variant.artifacts[0]
        self.assertIsInstance(artifact, DiscoveredArtifact)
        self.assertEqual(artifact.repository, REPO)
        self.assertEqual(artifact.filename, "model-Q4_K_M.gguf")
        self.assertEqual(artifact.format, "GGUF")
        self.assertEqual(artifact.declared_quantization, "Q4_K_M")
        self.assertIsNone(artifact.model_id)
        self.assertEqual(artifact.source, "huggingface")
        self.assertEqual(
            artifact.download_url,
            f"https://huggingface.co/{REPO}/resolve/main/model-Q4_K_M.gguf",
        )
        self.assertEqual(artifact.declared_size, 1234)
        self.assertEqual(artifact.declared_sha256, OID_Q4)
        self.assertEqual(artifact.revision, SHA)

    def test_revision_is_declared_sha_and_tree_uses_it(self):
        provider, calls = make_provider(inspect_routes())
        provider.inspect(REPO)
        self.assertIn(f"/tree/{SHA}?recursive=true", calls[1][0])

    def test_revision_none_when_missing_or_invalid(self):
        for sha in (None, "main", "abc", 40 * "z"):
            metadata = metadata_payload(sha=sha)
            provider, calls = make_provider(
                inspect_routes(metadata=metadata, tree=q4_tree())
            )
            (variant,) = provider.inspect(REPO)
            self.assertIsNone(variant.artifacts[0].revision, msg=repr(sha))
            self.assertIn("/tree/main?recursive=true", calls[1][0])

    def test_revision_missing_key(self):
        metadata = metadata_payload()
        del metadata["sha"]
        provider, calls = make_provider(
            inspect_routes(metadata=metadata, tree=q4_tree())
        )
        (variant,) = provider.inspect(REPO)
        self.assertIsNone(variant.artifacts[0].revision)
        self.assertIn("/tree/main?recursive=true", calls[1][0])

    def test_unmapped_repository_model_id_none(self):
        from castlearq.model_identity import logical_model_id

        self.assertIsNone(logical_model_id("huggingface", REPO))
        provider, _ = make_provider(inspect_routes(tree=q4_tree()))
        (variant,) = provider.inspect(REPO)
        self.assertIsNone(variant.artifacts[0].model_id)

    def test_no_gguf_repository_returns_empty(self):
        tree = [{"path": "README.md", "type": "file", "size": 10}]
        provider, _ = make_provider(inspect_routes(tree=tree))
        self.assertEqual(provider.inspect(REPO), ())

    def test_same_quantization_groups_artifacts(self):
        tree = [
            {"path": "b-Q4_K_M.gguf", "type": "file", "size": 2,
             "lfs": {"oid": OID_Q8}},
            {"path": "a-Q4_K_M.gguf", "type": "file", "size": 1,
             "lfs": {"oid": OID_Q4}},
        ]
        provider, _ = make_provider(inspect_routes(tree=tree))
        variants = provider.inspect(REPO)
        self.assertEqual(len(variants), 1)
        self.assertEqual(
            [a.filename for a in variants[0].artifacts],
            ["a-Q4_K_M.gguf", "b-Q4_K_M.gguf"],
        )

    def test_unknown_quantization_group(self):
        tree = [{"path": "plain-model.gguf", "type": "file", "size": 1,
                 "lfs": {"oid": OID_Q4}}]
        provider, _ = make_provider(inspect_routes(tree=tree))
        variants = provider.inspect(REPO)
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0].declared_quantization, "Unknown")
        self.assertEqual(variants[0].artifacts[0].declared_quantization, "Unknown")

    def test_deterministic_variant_ordering(self):
        provider_a, _ = make_provider(inspect_routes())
        provider_b, _ = make_provider(
            inspect_routes(tree=list(reversed(tree_payload())))
        )
        self.assertEqual(provider_a.inspect(REPO), provider_b.inspect(REPO))

    def test_non_gguf_entries_ignored(self):
        tree = tree_payload() + [
            {"path": "model.safetensors", "type": "file", "size": 9},
            {"path": "notes.gguf.txt", "type": "file", "size": 9},
        ]
        provider, _ = make_provider(inspect_routes(tree=tree))
        variants = provider.inspect(REPO)
        self.assertEqual(
            [v.declared_quantization for v in variants], ["Q4_K_M", "Q8_0"]
        )

    def test_missing_size_and_lfs_leave_declared_fields_none(self):
        tree = [{"path": "model-Q4_K_M.gguf", "type": "file"}]
        provider, _ = make_provider(inspect_routes(tree=tree))
        (variant,) = provider.inspect(REPO)
        artifact = variant.artifacts[0]
        self.assertIsNone(artifact.declared_size)
        self.assertIsNone(artifact.declared_sha256)

    def test_declared_size_falls_back_to_lfs(self):
        tree = [{"path": "model-Q4_K_M.gguf", "lfs": {"size": 77, "oid": OID_Q4}}]
        provider, _ = make_provider(inspect_routes(tree=tree))
        (variant,) = provider.inspect(REPO)
        self.assertEqual(variant.artifacts[0].declared_size, 77)

    def test_declared_sha256_lowercased(self):
        tree = [{"path": "model-Q4_K_M.gguf", "type": "file", "size": 1,
                 "lfs": {"oid": OID_Q4.upper()}}]
        provider, _ = make_provider(inspect_routes(tree=tree))
        (variant,) = provider.inspect(REPO)
        self.assertEqual(variant.artifacts[0].declared_sha256, OID_Q4)

    def test_xet_hash_not_accepted_as_sha(self):
        tree = [{"path": "model-Q4_K_M.gguf", "type": "file", "size": 1,
                 "lfs": {"xetHash": OID_Q4}}]
        provider, _ = make_provider(inspect_routes(tree=tree))
        (variant,) = provider.inspect(REPO)
        self.assertIsNone(variant.artifacts[0].declared_sha256)

    def test_invalid_size_rejected(self):
        for bad_size in (-1, True, 3.5, "100"):
            tree = [{"path": "model-Q4_K_M.gguf", "type": "file",
                     "size": bad_size}]
            provider, _ = make_provider(inspect_routes(tree=tree))
            with self.assertRaises(DiscoveryError):
                provider.inspect(REPO)

    def test_invalid_sha_rejected(self):
        for bad_oid in ("abc", "z" * 64, OID_Q4[:-1], ("1" * 64) + "ff"):
            tree = [{"path": "model-Q4_K_M.gguf", "type": "file", "size": 1,
                     "lfs": {"oid": bad_oid}}]
            provider, _ = make_provider(inspect_routes(tree=tree))
            with self.assertRaises(DiscoveryError):
                provider.inspect(REPO)

    def test_missing_optional_metadata(self):
        metadata = metadata_payload(author=None, tags=None, config=None)
        del metadata["sha"]
        provider, _ = make_provider(
            inspect_routes(metadata=metadata, tree=q4_tree())
        )
        (variant,) = provider.inspect(REPO)
        self.assertIsNone(variant.candidate.author)
        self.assertIsNone(variant.candidate.declared_architecture)
        self.assertEqual(variant.candidate.tags, ())
        self.assertIsNone(variant.artifacts[0].revision)

    def test_metadata_not_object_rejected(self):
        provider, _ = make_provider(inspect_routes(metadata=[]))
        with self.assertRaises(DiscoveryError):
            provider.inspect(REPO)

    def test_tree_not_list_rejected(self):
        provider, _ = make_provider(inspect_routes(tree={"error": "nope"}))
        with self.assertRaises(DiscoveryError):
            provider.inspect(REPO)

    def test_non_dict_tree_entries_skipped(self):
        tree = [42, None, {"path": "model-Q4_K_M.gguf", "type": "file",
                           "size": 1, "lfs": {"oid": OID_Q4}}]
        provider, _ = make_provider(inspect_routes(tree=tree))
        (variant,) = provider.inspect(REPO)
        self.assertEqual(len(variant.artifacts), 1)


class ErrorTests(unittest.TestCase):
    """AC8: external failures become DiscoveryError, never SourceError."""

    def test_http_error_maps_to_discovery_error(self):
        error = HTTPError("https://huggingface.co/api/models", 503,
                          "Service Unavailable", None, None)
        provider, _ = make_provider([("/api/", error)])
        with self.assertRaises(DiscoveryError) as caught:
            provider.search("x")
        self.assertIn("HTTP 503", str(caught.exception))
        provider, _ = make_provider(inspect_routes(metadata=error))
        with self.assertRaises(DiscoveryError):
            provider.inspect(REPO)

    def test_network_error_maps_to_discovery_error(self):
        for error in (URLError("dns failure"), TimeoutError("timed out"),
                      OSError("broken pipe")):
            provider, _ = make_provider([("/api/", error)])
            with self.assertRaises(DiscoveryError):
                provider.search("x")

    def test_invalid_json_maps_to_discovery_error(self):
        provider, _ = make_provider([("/api/", b"<html>not json</html>")])
        with self.assertRaises(DiscoveryError):
            provider.search("x")
        provider, _ = make_provider(inspect_routes(metadata=b"\xff\xfe\x00"))
        with self.assertRaises(DiscoveryError):
            provider.inspect(REPO)

    def test_invalid_transport_result_rejected(self):
        provider = HuggingFaceDiscoveryProvider(
            transport=lambda url, timeout: 42  # type: ignore[arg-type,return-value]
        )
        with self.assertRaises(DiscoveryError):
            provider.search("x")
        provider = HuggingFaceDiscoveryProvider(
            transport=lambda url, timeout: (b"[]", "not-a-mapping")  # type: ignore[arg-type,return-value]
        )
        with self.assertRaises(DiscoveryError):
            provider.search("x")

    def test_discovery_error_independent_from_source_error(self):
        self.assertFalse(issubclass(DiscoveryError, SourceError))
        self.assertIsNot(DiscoveryError, SourceError)
        provider, _ = make_provider([("/api/", URLError("down"))])
        try:
            provider.search("x")
        except DiscoveryError as error:
            self.assertFalse(isinstance(error, SourceError))
        except SourceError as error:  # pragma: no cover - must never happen
            self.fail(f"SourceError escaped: {error}")
        else:
            self.fail("no error raised")


class SecurityTests(unittest.TestCase):
    """AC9 / section 17: repository, filename, host and cursor controls."""

    def test_invalid_repository_rejected_before_request(self):
        provider, calls = make_provider(inspect_routes())
        for bad in ("../evil", "no-slash", "/absolute/repo", "a/../b",
                    "owner/", "/repo", "own er/repo", ""):
            with self.assertRaises(DiscoveryError):
                provider.inspect(bad)
        self.assertEqual(calls, [])

    def test_invalid_api_host_rejected(self):
        for api_base in ("http://huggingface.co/api",
                         "https://evil.example/api",
                         "ftp://huggingface.co/api",
                         "https://evil.example/?x=https://huggingface.co"):
            provider, calls = make_provider([("/api/", b"[]")])
            provider = HuggingFaceDiscoveryProvider(
                api_base=api_base, transport=provider.transport
            )
            with self.assertRaises(DiscoveryError):
                provider.search("x")
            with self.assertRaises(DiscoveryError):
                provider.inspect(REPO)
            self.assertEqual(calls, [])

    def test_invalid_filename_rejected(self):
        for bad_name in ("../evil.gguf", "..\\evil.gguf", "/abs.gguf",
                         "sub/dir.gguf", "./model.gguf", "dir/../model.gguf"):
            tree = [{"path": bad_name, "type": "file", "size": 1}]
            provider, _ = make_provider(inspect_routes(tree=tree))
            with self.assertRaises(DiscoveryError):
                provider.inspect(REPO)

    def test_search_and_inspect_only_touch_metadata(self):
        provider, calls = make_provider(
            [("/tree/", tree_payload()), (f"/models/{REPO}", metadata_payload()),
             ("/api/", search_payload())]
        )
        provider.search("llama", limit=3)
        provider.inspect(REPO)
        self.assertEqual(len(calls), 3)
        for url, timeout in calls:
            self.assertIn("https://huggingface.co/api/models", url)
            self.assertNotIn("/resolve/", url)
            self.assertEqual(timeout, 10.0)

    def test_declared_download_url_is_locator_only(self):
        provider, calls = make_provider(inspect_routes(tree=q4_tree()))
        (variant,) = provider.inspect(REPO)
        artifact = variant.artifacts[0]
        self.assertIn("/resolve/main/", artifact.download_url)
        for url, _ in calls:
            self.assertNotIn("/resolve/", url)


class IsolationTests(unittest.TestCase):
    """AC10 / AC11 / AC12 / L1 boundary."""

    FORBIDDEN_MODULES = (
        "models", "model_identity", "downloads", "model_store", "base",
        "huggingface", "main", "admission", "execution", "evaluation",
        "runtime", "downloader",
    )

    def test_no_forbidden_imports(self):
        for module in imported_modules():
            for forbidden in self.FORBIDDEN_MODULES:
                self.assertFalse(
                    module == forbidden or module.startswith(forbidden + "."),
                    f"forbidden import: {module}",
                )

    def test_no_acquisition_references_in_source(self):
        source = MODULE_PATH.read_text(encoding="utf-8").lower()
        for bad in ("artifactspec", "artifactstate", "downloadplanner",
                    "downloader", "modelstore", "model_identity",
                    "logical_model_id", "sourceerror", "runtime_artifact",
                    "verified_", "content_id", "local_path", "modelsource"):
            self.assertNotIn(bad, source)

    def test_no_file_write_calls(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"open", "write", "exec", "eval"})

    def test_discovery_contract_intact(self):
        digest = hashlib.sha256(DISCOVERY_PATH.read_bytes()).hexdigest()
        self.assertEqual(digest, DISCOVERY_SHA256)
        source = DISCOVERY_PATH.read_text(encoding="utf-8")
        self.assertIn("class ModelDiscovery", source)
        self.assertNotIn("huggingface", source.lower())

    def test_l1_declared_only(self):
        provider, _ = make_provider(inspect_routes(tree=q4_tree()))
        (variant,) = provider.inspect(REPO)
        artifact = variant.artifacts[0]
        for field in ("verified_sha256", "verified_quantization",
                      "content_id", "local_path", "state", "verdict"):
            self.assertFalse(hasattr(artifact, field))
            self.assertNotIn(field, DiscoveredArtifact.__dataclass_fields__)
            self.assertNotIn(field, ModelCandidate.__dataclass_fields__)
        self.assertIsNotNone(artifact.declared_sha256)
        self.assertTrue(artifact.download_url.startswith("https://"))


class SiblingTests(unittest.TestCase):
    """AC15: the provider is an independent sibling, not a source subclass."""

    def test_provider_is_not_a_model_source(self):
        self.assertFalse(issubclass(HuggingFaceDiscoveryProvider, ModelSource))
        self.assertFalse(issubclass(HuggingFaceDiscoveryProvider, HuggingFaceSource))
        self.assertIsNot(HuggingFaceDiscoveryProvider, HuggingFaceSource)

    def test_provider_does_not_wrap_huggingface_source(self):
        provider = HuggingFaceDiscoveryProvider()
        self.assertFalse(isinstance(provider, HuggingFaceSource))
        self.assertFalse(hasattr(provider, "discover_artifacts"))


if __name__ == "__main__":
    unittest.main()

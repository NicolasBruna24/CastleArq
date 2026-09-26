"""B9.54: the public surface is part of the contract, so it is tested.

B9.53 ratified what CastleArq may claim about itself. These tests assert the
claims that were ratified and reject the ones that were forbidden, so the public
surface cannot drift into overstating the product without failing the suite.

They are deliberately narrow. The guarantee-language check looks for an
unqualified assertion rather than banning ordinary English words, and the
vocabulary check bans internal architecture terms, not prose.
"""

from __future__ import annotations

import io
import sys
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from app.main import main

README = Path("README.md")
MAIN_PY = Path("app/main.py")
PYPROJECT = Path("pyproject.toml")
COMPATIBILITY_PY = Path("app/compatibility.py")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _flat(path: Path) -> str:
    """Whitespace-normalised text: the README is hard-wrapped, so phrases
    straddle newlines and must be compared without them."""
    return " ".join(_read(path).split())


def _help_text() -> str:
    """Render ``castlearq --help`` exactly as a user would see it."""
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        with mock.patch.object(sys, "argv", ["castlearq", "--help"]):
            with __import__("contextlib").suppress(SystemExit):
                main()
    return stdout.getvalue()


class PublicClaimTests(unittest.TestCase):
    """B9.53 sections 3-8: the ratified public claims."""

    def test_readme_states_the_primary_claim(self):
        flat = _flat(README)
        self.assertIn("checks whether a model can run on your machine", flat)
        self.assertIn("shows its work", flat)
        self.assertIn("refuses to run what it cannot justify running", flat)

    def test_readme_states_the_five_evaluated_conditions(self):
        """B9.53 section 4: the exact scope, not a vaguer one."""
        flat = _flat(README)
        for condition in (
            "artifact–model identity",
            "artifact format support",
            "model architecture support",
            "runtime artifact support",
            "runtime backend support",
        ):
            self.assertIn(condition, flat)

    def test_readme_has_a_verdict_scope_section(self):
        """B9.53 section 11: state plainly what is NOT established."""
        text = _read(README)
        self.assertIn("## What the verdict does not cover", text)
        flat = " ".join(text.split())
        for excluded in (
            "memory sufficiency",
            "output quality",
            "model behaviour",
            "security or safety",
            "performance",
            "absence of crashes or runtime failures",
        ):
            self.assertIn(excluded, flat)

    def test_readme_states_the_runtime_relationship(self):
        """B9.53 section 7: CastleArq drives llama.cpp, it does not replace it."""
        flat = _flat(README)
        self.assertIn(
            "does not replace llama.cpp and does not perform inference itself",
            flat,
        )
        self.assertIn(
            "is the runtime that loads the model and generates text", flat
        )

    def test_readme_states_the_audience_and_requirements(self):
        """B9.53 section 9: do not hide the technical prerequisites."""
        flat = _flat(README)
        self.assertIn(
            "developers already working with local AI models on Linux", flat
        )
        self.assertIn("It is not a consumer application.", flat)
        self.assertIn("exercised baseline", flat)

    def test_readme_discloses_the_published_version(self):
        """B9.53 section 17: do not imply v0.1.0 already has this surface."""
        flat = _flat(README)
        self.assertIn("The published PyPI release is `0.1.0`", flat)
        # Compared without the leading sentence so the blockquote marker
        # inserted when the line is wrapped cannot affect the match.
        self.assertIn("current `main` branch", flat)
        self.assertIn("ahead of that release", flat)

    def test_readme_demonstration_is_a_real_transcript(self):
        """B9.53 section 16: real evidence, with any elision declared."""
        text = _read(README)
        self.assertIn("### A real run", text)
        self.assertIn("Evidence (observed):", text)
        self.assertIn("CASTLEARQ_OK", text)
        self.assertIn("elided", text)
        self.assertIn("Nothing in it is hand-written.", text)



class ForbiddenClaimTests(unittest.TestCase):
    """B9.53 section 8: out-of-scope claims must not appear."""

    def test_public_prose_makes_no_unqualified_guarantee(self):
        """Fail on an unqualified guarantee in PROSE, not on the word.

        Scoped to the README and to the CLI description string. Source code is
        excluded on purpose: identifiers such as ``UnsafePathError`` contain
        "safe" without ever being a claim about the product.

        A line is only a violation when it asserts safe/secure/reliable/
        guaranteed without a negation in the same sentence, so honest prose
        such as "makes no claim to be safer" is left alone.
        """
        negations = ("not ", "no ", "never", "cannot", "without", "neither",
                     "is not", "are not")
        banned = ("safe", "secure", "reliable", "guaranteed", "guarantee")
        for path in (README,):
            for number, line in enumerate(_read(path).splitlines(), start=1):
                lowered = line.lower()
                for word in banned:
                    if word not in lowered:
                        continue
                    if not any(neg in lowered for neg in negations):
                        self.fail(
                            f"{path}:{number} uses '{word}' as an unqualified "
                            f"claim about CastleArq: {line.strip()!r}"
                        )

    def test_cli_description_makes_no_unqualified_guarantee(self):
        """The one-line description is the most-read sentence in the product."""
        description = _help_text().splitlines()[4]
        for word in ("safe", "secure", "reliable", "guaranteed"):
            self.assertNotIn(word, description.lower())

    def test_readme_avoids_internal_architecture_vocabulary(self):
        """B9.53 section 11: internal vocabulary must not be the public voice."""
        flat = _flat(README).lower()
        for internal in (
            "composition root",
            "fail-closed",
            "admission seam",
            "use case",
        ):
            self.assertNotIn(internal, flat)

    def test_readme_avoids_comparative_claims(self):
        """B9.53 section 8: no comparison with another product is in scope.

        ``localai`` is allowed in exactly one place: the legacy store path
        ``~/.local/share/localai-hub/models``, which is path compatibility the
        product genuinely implements, not a comparison. Any other mention would
        be a comparison and is rejected.
        """
        flat = _flat(README).lower()
        for other in ("ollama", "lm studio"):
            self.assertNotIn(
                other, flat,
                "a comparison with another product is explicitly deferred",
            )
        if "localai" in flat:
            # Allowed only as part of the legacy filesystem path.
            self.assertIn("localai-hub/models", flat)
            without_legacy = flat.replace("localai-hub/models", "")
            self.assertNotIn("localai", without_legacy)


class PublicLanguageTests(unittest.TestCase):
    """B9.53 section 10: English-first, applied to every public surface."""

    def test_readme_is_english(self):
        flat = _flat(README)
        for spanish in (
            "CastleArq es", "Verificación", "advertencia", "Diagnóstico",
            "El runtime", "descarga el", "No hay", "La memoria",
            "Requiere usar RAM", "sesión de chat",
        ):
            self.assertNotIn(spanish, flat)

    def test_cli_help_is_english(self):
        help_text = _help_text()
        for spanish in (
            "Ejecuta", "Verificación", "advertencia", "sesión",
            "Diagnóstico", "descarga",
        ):
            self.assertNotIn(spanish, help_text)

    def test_runtime_messages_are_english(self):
        """The runtime surface, not just the documents."""
        source = _read(COMPATIBILITY_PY)
        for spanish in (
            "No hay", "La memoria", "Requiere usar RAM", "El uso de RAM",
            "es una estimación",
        ):
            self.assertNotIn(spanish, source)

    def test_cli_description_states_the_differentiator(self):
        help_text = _help_text()
        self.assertIn("compatibility evaluation", help_text)
        self.assertIn("admitted execution", help_text)
        self.assertIn("llama.cpp", help_text)



class PackageMetadataTests(unittest.TestCase):
    """B9.53 section 13: the PyPI page must be legible and honest."""

    @classmethod
    def setUpClass(cls):
        cls.project = tomllib.loads(_read(PYPROJECT))["project"]

    def test_summary_is_user_facing(self):
        summary = self.project["description"]
        self.assertNotIn("Architecture", summary)
        self.assertIn("GGUF", summary)
        self.assertIn("evidence", summary)

    def test_long_description_comes_from_the_readme(self):
        readme = self.project["readme"]
        self.assertEqual(readme["file"], "README.md")
        self.assertEqual(readme["content-type"], "text/markdown")

    def test_development_status_is_alpha_not_beta(self):
        classifiers = self.project["classifiers"]
        self.assertIn("Development Status :: 3 - Alpha", classifiers)
        self.assertNotIn("Development Status :: 4 - Beta", classifiers)

    def test_required_classifiers_are_present(self):
        classifiers = set(self.project["classifiers"])
        for required in (
            "Intended Audience :: Developers",
            "Environment :: Console",
            "Operating System :: POSIX :: Linux",
            "Topic :: Scientific/Engineering :: Artificial Intelligence",
        ):
            self.assertIn(required, classifiers)

    def test_platform_claims_are_not_broadened(self):
        """Only Linux is exercised, so no other OS may be claimed."""
        classifiers = self.project["classifiers"]
        for other in ("Operating System :: Microsoft", "Operating System :: MacOS"):
            self.assertFalse(
                [c for c in classifiers if c.startswith(other)],
                f"unevidenced platform claim: {other}",
            )

    def test_no_license_classifier_conflicts_with_the_license_expression(self):
        """PEP 639: a License classifier alongside ``license = "Apache-2.0"``
        makes setuptools refuse to build. Found the hard way during B9.54 when
        the wheel build failed; keep it from coming back.
        """
        classifiers = self.project["classifiers"]
        self.assertFalse(
            [c for c in classifiers if c.startswith("License ::")],
            "PEP 639 supersedes license classifiers; the SPDX license "
            "expression already declares the license",
        )
        self.assertEqual(self.project["license"], "Apache-2.0")

    def test_project_urls_are_real_destinations(self):
        urls = self.project["urls"]
        self.assertEqual(
            set(urls), {"Homepage", "Repository"},
            "only pre-existing, real URLs may be declared",
        )
        for url in urls.values():
            self.assertTrue(url.startswith("https://"), url)

    def test_python_requirement_is_preserved(self):
        self.assertEqual(self.project["requires-python"], ">=3.10")


if __name__ == "__main__":
    unittest.main()


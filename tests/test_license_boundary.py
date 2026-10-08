# SPDX-FileCopyrightText: 2026 Marussa Metocharaki
# SPDX-License-Identifier: AGPL-3.0-only
"""
License-boundary guard.

`hsr/` is licensed Apache-2.0; the rest of the repository is AGPL-3.0.
That split only stays clean if `hsr/` never depends on AGPL code.
This test fails if any file in `hsr/`:
  1. imports anything except the Python standard library or `hsr` itself, or
  2. is missing the Apache-2.0 SPDX header, or
  3. if `hsr/LICENSE` or `hsr/NOTICE` is missing.

Run from the repository root:
    python -m unittest tests.test_license_boundary -v
"""
import ast
import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HSR_DIR = REPO_ROOT / "hsr"
ALLOWED_THIRD_PARTY = {"hsr"}  # the package itself
SPDX_LINE = "# SPDX-License-Identifier: Apache-2.0"


def _imported_top_level_names(path: pathlib.Path):
    """Yield (module_name, line_number, is_relative) for every import in a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0], node.lineno, False
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                yield "(relative)", node.lineno, True
            elif node.module:
                yield node.module.split(".")[0], node.lineno, False


class TestHsrLicenseBoundary(unittest.TestCase):
    def test_hsr_files_exist(self):
        files = sorted(HSR_DIR.glob("*.py"))
        self.assertTrue(files, "No Python files found in hsr/")

    def test_license_and_notice_present(self):
        self.assertTrue((HSR_DIR / "LICENSE").is_file(), "hsr/LICENSE is missing")
        self.assertTrue((HSR_DIR / "NOTICE").is_file(), "hsr/NOTICE is missing")
        text = (HSR_DIR / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("Apache License", text)
        self.assertIn("Version 2.0, January 2004", text)

    def test_hsr_imports_only_stdlib_or_hsr(self):
        stdlib = set(sys.stdlib_module_names)  # Python 3.10+
        problems = []
        for path in sorted(HSR_DIR.glob("*.py")):
            for name, lineno, is_relative in _imported_top_level_names(path):
                if is_relative:
                    continue  # relative imports stay inside hsr/
                if name in stdlib or name in ALLOWED_THIRD_PARTY:
                    continue
                problems.append(f"{path.name}:{lineno} imports '{name}'")
        self.assertEqual(
            problems, [],
            "hsr/ must not import non-stdlib modules (AGPL contamination risk): "
            + "; ".join(problems),
        )

    def test_every_hsr_python_file_has_apache_spdx_header(self):
        missing = []
        for path in sorted(HSR_DIR.glob("*.py")):
            head = path.read_text(encoding="utf-8").splitlines()[:5]
            if SPDX_LINE not in head:
                missing.append(path.name)
        self.assertEqual(missing, [], f"Missing Apache-2.0 SPDX header: {missing}")


if __name__ == "__main__":
    unittest.main()

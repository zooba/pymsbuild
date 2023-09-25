import os
import pytest
import sys

from pathlib import Path, PurePath

ROOT = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(ROOT))

import pymsbuild
import pymsbuild._generate as G
import pymsbuild._types as T


def find_names(source, pattern, basename=None):
    if basename is None:
        basename = PurePath("test") / pattern
    return {PurePath(n) for n, p in G._resolve_wildcards(basename, source, pattern)}


def find_paths(source, pattern, basename=None):
    if basename is None:
        basename = PurePath("test") / pattern
    return {p for n, p in G._resolve_wildcards(basename, source, pattern)}


class TestWildcards:
    def test_basic(self):
        expect = {PurePath("test/_msbuild.py")}
        assert find_names(ROOT, "_msbuild.py") == expect
        assert find_names(ROOT, "_msbu*.py") == expect
        assert find_names(ROOT, "*ild.py") == expect
        assert find_names(ROOT, "_msbuild.*") == expect
        assert find_names(ROOT, "?m?b?i?d.?y") == expect

        expect = {PurePath("test/pymsbuild/__main__.py")}
        assert find_names(ROOT, "pymsbuild/__main__.py") == expect
        assert find_names(ROOT, "*/__main__.py") == expect
        assert find_names(ROOT, "*/__m*__.py") == expect
        assert find_names(ROOT, "*/__m???__.py") == expect
        assert find_names(ROOT, "pymsb*/__main__.py") == expect
        assert find_names(ROOT, "pyms?uild/__main__.py") == expect

    def test_recursive(self):
        expect = {PurePath("test/tests/testcython/_msbuild.py"), PurePath("test/tests/testdata/_msbuild.py")}
        assert find_names(ROOT, "**/_msbuild.py") > expect
        assert find_names(ROOT, "tests/**/_msbuild.py") > expect
        assert find_names(ROOT, "tests/*/_msbuild.py") > expect
        assert find_names(ROOT, "tests/test*/_msbuild.py") > expect
        assert find_names(ROOT, "*/test*/_msbuild.py") > expect
        assert find_names(ROOT, "**/test*/_msbuild.py") > expect

    def test_no_traversal(self):
        # These patterns include part of ROOT, and so should not match
        # This is particularly important for the '**' pattern.
        assert not find_names(ROOT / "tests", "*/tests/testdata/_msbuild.py")
        assert not find_names(ROOT / "tests", "**/tests/testdata/_msbuild.py")

    def test_basename_unchanged_without_wildcard(self):
        BN = "X/Y/Z/__init__.py"
        assert find_names(ROOT, "_msbuild.py", BN) == {PurePath("X/Y/Z/__init__.py")}
        assert find_names(ROOT, "_msbuil?.py", BN) == {PurePath("X/Y/Z/_msbuild.py")}

        assert find_names(ROOT / "tests", "testdata/_msbuild.py", BN) == {PurePath("X/Y/Z/__init__.py")}
        assert find_names(ROOT / "tests", "testdata/_msbuil?.py", BN) == {PurePath("X/Y/testdata/_msbuild.py")}
        assert find_names(ROOT / "tests", "*/_msbuild.py", BN) > {PurePath("X/Y/testdata/_msbuild.py")}

        assert find_names(ROOT, "tests/testdata/_msbuild.py", BN) == {PurePath("X/Y/Z/__init__.py")}
        assert find_names(ROOT, "tests/*/_msbuild.py", BN) > {PurePath("X/tests/testdata/_msbuild.py")}
        assert find_names(ROOT, "test*/*/_msbuild.py", BN) > {PurePath("X/tests/testdata/_msbuild.py")}

        assert find_names(ROOT, ROOT / "tests/testdata/_msbuild.py", BN) == {PurePath("X/Y/Z/__init__.py")}
        assert find_names(ROOT, ROOT / "tests/*/_msbuild.py", BN) > {PurePath("X/Y/testdata/_msbuild.py")}
        assert find_names(ROOT, ROOT / "*/testdata/_msbuild.py", BN) == {PurePath("X/tests/testdata/_msbuild.py")}

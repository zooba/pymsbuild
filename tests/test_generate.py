import os
import pytest
import sys

from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pymsbuild
from pymsbuild import Package, PyFile


def test_simple_collect():
    p = Package("test",
        PyFile("testdata/f.py"),
        Package("subtest",
            PyFile("testdata/f-1.py", "f"),
        )
    )
    print(*pymsbuild.list_output("."), sep="\n")
    assert 0
    src = list(p._get_sources(".", None))
    assert {i[2] for i in src} == {"test\\f.py", "test\\subtest\\f.py"}



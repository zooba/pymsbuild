import os
import pytest
import sys

from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pymsbuild
from pymsbuild import Package, PyFile, Metadata
from pymsbuild._build import BuildState


@pytest.fixture
def built_projects():
    old = pymsbuild._TO_BUILD
    pymsbuild._TO_BUILD = b = []
    try:
        yield b
    finally:
        pymsbuild._TO_BUILD = old


def test_simple_collect(built_projects):
    Package("test",
        Metadata(version="1.0.0"),
        PyFile("testdata/f.py"),
        Package("subtest",
            PyFile("testdata/f-1.py", "f"),
        )
    ).build()
    p = built_projects[0]
    print(*pymsbuild.list_output("."), sep="\n")
    assert 0
    src = list(p._get_sources(".", None))
    assert {i[2] for i in src} == {"test\\f.py", "test\\subtest\\f.py"}


def test_glob_collect(built_projects):
    Package("stdlib",
        PyFile.collect(r"Lib\*.py"),
        Package("encodings",
            PyFile.collect(r"Lib\encodings\*.py")
        ),
    ).build()
    p = built_projects[0]
    src = list(p._get_sources(sys.base_prefix, lambda p: Path(p).parent.glob(p.name)))
    missing = {i[1] for i in src if not i[1].is_file()}
    assert not missing
    assert {i[2] for i in src} > {"stdlib\\__future__.py", "stdlib\\os.py", "stdlib\\encodings\\utf_8.py"}

"""
def test_generate(built_projects):
    Package("test",
        Metadata(version="1.0.0"),
        PyFile("
        """
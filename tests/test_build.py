import os
import pytest
import sys

from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pymsbuild
import pymsbuild._generate as G
import pymsbuild._types as T
from pymsbuild._build import locate as locate_msbuild

# Avoid calling locate() for each test
os.environ["MSBUILD"] = str(locate_msbuild())


@pytest.fixture
def build_state(tmp_path, testdata):
    bs = pymsbuild.BuildState()
    bs.source_dir = testdata
    bs.output_dir = tmp_path / "out"
    bs.build_dir = tmp_path / "build"
    bs.temp_dir = tmp_path / "temp"
    bs.package = T.Package("package",
        T.PyFile(testdata / "empty.py", "__init__.py"),
        T.PydFile("mod",
            T.CSourceFile(testdata / "mod.c"),
            TargetExt=".pyd",
        ),
    )
    bs.metadata = {"Name": "package", "Version": "1.0"}
    return bs


def test_build(build_state):
    bs = build_state
    bs.generate()
    bs.target = "Build"
    bs.build()

    files = {str(p.relative_to(bs.build_dir)) for p in bs.build_dir.rglob("**\\*.*")}
    assert files
    assert not (bs.build_dir / "PKG-INFO").is_file()
    assert files > {"package\\__init__.py", "package\\mod.pyd"}
    assert "pyproject.toml" not in files

    bs.target = "Clean"
    bs.build()
    files = {str(p.relative_to(bs.build_dir)) for p in bs.build_dir.rglob("**\\*.*")}
    assert not files


def test_build_sdist(build_state):
    bs = build_state
    bs.generate()
    bs.build_sdist()

    files = {str(p.relative_to(bs.build_dir)) for p in bs.build_dir.rglob("**\\*.*")}
    assert files == {"empty.py", "mod.c", "pyproject.toml", "_msbuild.py"}
    assert (bs.build_dir / "PKG-INFO").is_file()
    files = {str(p.relative_to(bs.output_dir)) for p in bs.output_dir.rglob("**\\*.*")}
    assert len(files) == 1
    f = next(iter(files))
    assert f.endswith(".tar.gz")

    bs.target = "Clean"
    bs.build()
    files = {str(p.relative_to(bs.build_dir)) for p in bs.build_dir.rglob("**\\*.*")}
    assert not files


@pytest.mark.parametrize("proj", ["testcython", "testproject1"])
def test_build_test_project(build_state, proj):
    bs = build_state
    bs.source_dir = bs.source_dir.parent / proj
    bs.generate()
    bs.build()

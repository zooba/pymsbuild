import os
import pytest
import subprocess
import sys

from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pymsbuild
import pymsbuild._generate as G
import pymsbuild._types as T
from pymsbuild._build import _locate_msbuild, BuildState

# Avoid calling locate() for each test
if not os.getenv("MSBUILD"):
    os.environ["MSBUILD"] = " ".join(_locate_msbuild())
    if os.environ["MSBUILD"] != " ".join(_locate_msbuild()):
        # We can't avoid it for some reason...
        del os.environ["MSBUILD"]


@pytest.fixture
def build_state(tmp_path, testdata):
    bs = BuildState()
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


@pytest.mark.parametrize("configuration", ["Debug", "Release"])
def test_build(build_state, configuration):
    os.environ["BUILD_BUILDNUMBER"] = "1"
    bs = build_state
    bs.generate()
    del os.environ["BUILD_BUILDNUMBER"]
    bs.target = "Build"
    bs.configuration = configuration
    bs.build()

    files = {p.relative_to(bs.build_dir) for p in bs.build_dir.rglob("**/*.*")}
    assert files
    assert not (bs.build_dir / "PKG-INFO").is_file()
    assert files > {Path(p) for p in {"package/__init__.py", "package/mod.pyd"}}
    assert "pyproject.toml" not in files

    bs.target = "Clean"
    bs.build()
    files = {p.relative_to(bs.build_dir) for p in bs.build_dir.rglob("**/*.*")}
    assert not files


@pytest.mark.parametrize("configuration", ["Debug", "Release"])
def test_build_sdist(build_state, configuration):
    bs = build_state
    bs.generate()
    bs.configuration = configuration
    bs.build_sdist()

    files = {p.relative_to(bs.build_dir) for p in bs.build_dir.rglob("**/*.*")}
    assert files == {Path(p) for p in {"empty.py", "mod.c", "pyproject.toml", "_msbuild.py"}}
    assert (bs.build_dir / "PKG-INFO").is_file()
    files = {p.relative_to(bs.output_dir) for p in bs.output_dir.rglob("**/*.*")}
    assert len(files) == 1
    f = next(iter(files))
    assert f.match("*.tar.gz")

    bs.target = "Clean"
    bs.build()
    files = {p.relative_to(bs.build_dir) for p in bs.build_dir.rglob("**/*.*")}
    assert not files


@pytest.mark.parametrize("proj", ["testcython", "testproject1", "testpurepy"])
@pytest.mark.parametrize("configuration", ["Debug", "Release"])
def test_build_test_project(build_state, proj, configuration):
    bs = build_state
    bs.source_dir = bs.source_dir.parent / proj
    bs.package = None
    bs.generate()
    bs.configuration = configuration
    bs.build()


@pytest.mark.parametrize("configuration", ["Debug", "Release"])
def test_dllpack(build_state, configuration):
    bs = build_state
    bs.source_dir = bs.source_dir.parent / "testdllpack"
    bs.package = None
    bs.generate()
    bs.configuration = configuration
    bs.build()
    print(bs.build_dir)
    print(list(bs.build_dir.glob("*")))
    subprocess.check_call(
        [sys.executable, str(bs.source_dir / "test-dllpack.py")],
        env={**os.environ, "PYTHONPATH": str(bs.build_dir)}
    )

import os
import pytest
import subprocess
import sys
import zipfile

from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pymsbuild
import pymsbuild._generate as G
import pymsbuild._types as T
from pymsbuild._build import locate_msbuild, BuildState

# Avoid calling locate() for each test
if not os.getenv("MSBUILD"):
    os.environ["MSBUILD"] = " ".join(locate_msbuild())
    if os.environ["MSBUILD"] != " ".join(locate_msbuild()):
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

    files = {p.relative_to(bs.build_dir) for p in bs.build_dir.rglob("**/*")}
    assert files
    assert not (bs.build_dir / "PKG-INFO").is_file()
    assert files >= {Path(p) for p in {"package/__init__.py", "package/mod.pyd"}}
    assert "pyproject.toml" not in files

    bs.target = "Clean"
    bs.build()
    files = {p.relative_to(bs.build_dir) for p in bs.build_dir.rglob("**/*")}
    assert not files


@pytest.mark.parametrize("configuration", ["Debug", "Release"])
def test_build_sdist(build_state, configuration):
    bs = build_state
    bs.generate()
    bs.configuration = configuration
    bs.build_sdist()

    files = {p.relative_to(bs.build_dir) for p in bs.build_dir.rglob("**/*")}
    assert files == {Path(p) for p in {"empty.py", "mod.c", "pyproject.toml", "_msbuild.py"}}
    assert (bs.build_dir / "PKG-INFO").is_file()
    files = {p.relative_to(bs.output_dir) for p in bs.output_dir.rglob("**/*")}
    assert len(files) == 1
    f = next(iter(files))
    assert f.match("*.tar.gz")

    bs.target = "Clean"
    bs.build()
    files = {p.relative_to(bs.build_dir) for p in bs.build_dir.rglob("**/*")}
    assert not files


def test_build_sdist_layout(build_state):
    bs = build_state
    bs.layout_dir = bs.temp_dir / "layout"
    bs.generate()
    bs.build_sdist()

    files = {str(p.relative_to(bs.output_dir)) for p in bs.output_dir.rglob("**/*")}
    assert not files

    bs2 = BuildState()
    bs2.layout_dir = bs.layout_dir
    bs2.pack()

    files = {str(p.relative_to(bs2.output_dir)) for p in Path(bs2.output_dir).rglob("**/*")}
    assert len(files) == 1
    f = next(iter(files))
    assert f.endswith(".tar.gz")


def test_build_wheel_layout(build_state):
    bs = build_state
    bs.layout_dir = bs.temp_dir / "layout"
    bs.generate()
    bs.build_wheel()

    files = {str(p.relative_to(bs.output_dir)) for p in bs.output_dir.rglob("**/*")}
    assert not files

    files = {p.relative_to(bs.layout_dir) for p in bs.layout_dir.rglob("**/*")}
    assert not [p for p in files if p.match("*.dist-info/RECORD")]

    bs2 = BuildState()
    bs2.layout_dir = bs.layout_dir
    bs2.pack()

    files = {str(p.relative_to(bs2.output_dir)) for p in Path(bs2.output_dir).rglob("**/*")}
    assert len(files) == 1
    f = next(iter(files))
    assert f.endswith(".whl")

    with zipfile.ZipFile(Path(bs2.output_dir) / f, 'r') as zf:
        files = set(zf.namelist())
    files = [p for p in files if Path(p).match("*.dist-info/RECORD")]
    assert len(files) == 1


@pytest.mark.parametrize("proj", ["testcython", "testproject1", "testpurepy"])
@pytest.mark.parametrize("configuration", ["Debug", "Release"])
def test_build_test_project(build_state, proj, configuration):
    bs = build_state
    bs.source_dir = bs.source_dir.parent / proj
    bs.package = None
    bs.verbose = True
    bs.generate()
    bs.configuration = configuration
    bs.build()


@pytest.mark.parametrize("configuration", ["Debug", "Release"])
@pytest.mark.skipif(sys.platform not in {"win32"}, reason="Only supported on Windows")
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

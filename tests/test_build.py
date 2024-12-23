import os
import pytest
import subprocess
import sys
import zipfile

from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

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
    bs.verbose = True
    bs.source_dir = testdata / "testdata"
    bs.output_dir = tmp_path / "out"
    bs.build_dir = tmp_path / "build"
    bs.layout_dir = tmp_path / "layout"
    bs._perform_layout = False  # allows us to override layout_dir
    bs.temp_dir = tmp_path / "temp"
    bs.package = T.Package("package",
        T.PyFile(testdata / "testdata/empty.py", "__init__.py"),
        T.PydFile("mod",
            T.CSourceFile(testdata / "testdata/mod.c"),
            T.VersionInfo(
                ProductName="package",
                FileDescription="The package module",
                FileVersion="1.0",
                FILEVERSION="1,0,0,0",
                ProductVersion="1.0",
                PRODUCTVERSION="1,0,0,0",
            ),
            TargetExt=".pyd",
        ),
    )
    bs.metadata = {"Name": "package", "Version": "1.0"}
    return bs


def dump_layout_dir(bs):
    print(bs.layout_dir)
    print(*[f"- {f.relative_to(bs.layout_dir)}" for f in bs.layout_dir.rglob("*")], sep="\n")


@pytest.mark.parametrize("configuration", ["Debug", "Release"])
def test_build(build_state, configuration):
    os.environ["BUILD_BUILDNUMBER"] = "1"
    bs = build_state
    bs.finalize(in_place=True)
    assert not bs._perform_layout
    bs.generate()
    del os.environ["BUILD_BUILDNUMBER"]
    bs.target = "Build"
    bs.configuration = configuration
    bs.build()

    files = {p.relative_to(bs.build_dir) for p in bs.build_dir.rglob("**/*") if p.is_file()}
    assert files
    assert not (bs.build_dir / "PKG-INFO").is_file()
    if sys.platform == "win32":
        assert files >= {Path(p) for p in {"package/mod.pdb", "package/mod.pyd"}}
    else:
        assert files >= {Path(p) for p in {"package/mod.pyd"}}
    assert "pyproject.toml" not in files
    assert "package/__init__.py" not in files
    
    files = {p.relative_to(bs.source_dir) for p in bs.source_dir.rglob("**/*") if p.is_file()}
    assert files
    assert files >= {Path(p) for p in {"package/__init__.py", "package/mod.pyd"}}

    bs.target = "Clean"
    bs.build()
    files = {p.relative_to(bs.build_dir) for p in bs.build_dir.rglob("**/*") if p.is_file()}
    assert not files
    files = {p.relative_to(bs.source_dir) for p in bs.source_dir.rglob("**/*") if p.is_file()}
    assert files >= {Path(p) for p in {"empty.py"}}
    assert not files & {Path(p) for p in {"package/__init__.py", "package/mod.pyd"}}

@pytest.mark.parametrize("configuration", ["Debug", "Release"])
def test_build_sdist(build_state, configuration):
    bs = build_state
    bs.finalize(sdist=True)
    assert not bs._perform_layout
    bs.generate()
    bs.configuration = configuration
    bs.build_sdist()

    files = {p.relative_to(bs.layout_dir / "package-1.0") for p in bs.layout_dir.rglob("**/*") if p.is_file()}
    assert files == {Path(p) for p in {"PKG-INFO", "empty.py", "mod.c", "pyproject.toml", "_msbuild.py"}}
    files = {p.relative_to(bs.output_dir) for p in bs.output_dir.rglob("**/*") if p.is_file()}
    assert len(files) == 1
    f = next(iter(files))
    assert f.match("*.tar.gz")

    bs.target = "Clean"
    bs.build()
    files = {p.relative_to(bs.layout_dir) for p in bs.layout_dir.rglob("**/*") if p.is_file()}
    assert not files


def test_build_sdist_layout(build_state):
    bs = build_state
    bs.finalize(sdist=True)
    bs.generate()
    bs.layout_sdist()

    files = {str(p.relative_to(bs.output_dir)) for p in bs.output_dir.rglob("**/*") if p.is_file()}
    assert not files

    bs2 = BuildState()
    bs2.layout_dir = bs.layout_dir
    bs2.pack()

    files = {str(p.relative_to(bs2.output_dir)) for p in Path(bs2.output_dir).rglob("**/*") if p.is_file()}
    assert len(files) == 1
    f = next(iter(files))
    assert f.endswith(".tar.gz")


def test_build_wheel_layout(build_state):
    bs = build_state
    bs.verbose = True
    bs.finalize()
    bs.generate()
    bs.layout_wheel()

    files = {str(p.relative_to(bs.output_dir)) for p in bs.output_dir.rglob("**/*")}
    assert not files

    files = {p.relative_to(bs.layout_dir) for p in bs.layout_dir.rglob("**/*")}
    assert not [p for p in files if p.match("*.dist-info/RECORD")]

    print("*" * 80)
    bs2 = BuildState()
    bs2.verbose = True
    bs2.layout_dir = bs.layout_dir
    bs2.pack()

    files = {str(p.relative_to(bs2.output_dir)) for p in Path(bs2.output_dir).rglob("**/*") if p.is_file()}
    assert len(files) == 1
    f = next(iter(files))
    assert f.endswith(".whl")

    with zipfile.ZipFile(Path(bs2.output_dir) / f, 'r') as zf:
        files = set(zf.namelist())
    print("Wheel contents:", *files, sep="\n")
    records = [p for p in files if Path(p).match("*.dist-info/RECORD")]
    assert len(records) == 1
    states = [p for p in files if Path(p).match("__state.txt")]
    assert not states


@pytest.mark.parametrize("proj", ["testcython", "testproject1", "testpurepy"])
@pytest.mark.parametrize("configuration", ["Debug", "Release"])
def test_build_test_project(build_state, testdata, proj, configuration):
    bs = build_state
    bs.source_dir = testdata / proj
    bs.package = None
    bs.verbose = True
    bs.finalize()
    bs.generate()
    bs.configuration = configuration
    bs.build()


@pytest.mark.parametrize("configuration", ["Debug", "Release"])
def test_dllpack(build_state, testdata, configuration):
    bs = build_state
    bs.source_dir = testdata / "testdllpack"
    bs.package = None
    bs.verbose = True
    bs.finalize()
    bs.generate()
    bs.configuration = configuration
    bs.build()
    dump_layout_dir(bs)
    subprocess.check_call(
        [sys.executable, str(bs.source_dir / "test-dllpack.py")],
        env={**os.environ, "PYTHONPATH": str(bs.layout_dir)}
    )

@pytest.mark.parametrize("configuration", ["Debug", "Release"])
@pytest.mark.parametrize("encrypt", [b"a-bytes-key-0123", "a-str-key-01234567890123"])
@pytest.mark.skipif(sys.platform not in {"win32"}, reason="Only supported on Windows")
def test_dllpack_encrypted(build_state, testdata, configuration, encrypt):
    if not isinstance(encrypt, str):
        import base64
        encrypt = "base64:" + base64.b64encode(encrypt).decode("ascii")
    bs = build_state
    bs.source_dir = testdata / "testdllpack"
    bs.package = None
    bs.verbose = True
    bs.finalize()
    bs.package.options["EncryptionKeyVariable"] = "PYMSBUILD_ENCRYPT_KEY"
    bs.generate()
    bs.configuration = configuration
    os.environ["PYMSBUILD_ENCRYPT_KEY"] = encrypt
    bs.build()
    del os.environ["PYMSBUILD_ENCRYPT_KEY"]
    dump_layout_dir(bs)
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.check_call(
            [sys.executable, str(bs.source_dir / "test-dllpack.py"), "-p"],
            cwd=bs.layout_dir,
            env={**os.environ, "PYTHONPATH": str(bs.layout_dir), "PYMSBUILD_ENCRYPT_KEY": ""}
        )
    subprocess.check_call(
        [sys.executable, str(bs.source_dir / "test-dllpack.py"), "-p"],
        cwd=bs.layout_dir,
        env={**os.environ, "PYTHONPATH": str(bs.layout_dir), "PYMSBUILD_ENCRYPT_KEY": encrypt}
    )


def build_testpyproject(config, version, tmp_path, testdata):
    source = testdata / "testpyproject"
    layout = tmp_path / "out"
    subprocess.check_call(
        [sys.executable, "-m", "pymsbuild", "sdist", "-c", config],
        cwd=str(source),
        env={**os.environ, "PYTHONPATH": ROOT, "PYMSBUILD_LAYOUT_DIR": str(layout)},
    )
    layout /= f"testpyproject-{version}"
    assert {str(f.relative_to(layout)) for f in layout.rglob("*")} \
           == {"PKG-INFO", "pyproject.toml", "_msbuild.py"}
    pyproj = (layout / "pyproject.toml").read_text(encoding="utf-8").splitlines()
    source = (source / "pyproject.toml").read_text(encoding="utf-8").splitlines()
    pkgconf = (layout / "PKG-INFO").read_text(encoding="utf-8").splitlines()
    return pyproj, source, pkgconf


def test_pyproject_copy(tmp_path, testdata):
    pyproj, source, pkgconf = build_testpyproject("_msbuild.py", "0.0.1", tmp_path, testdata)
    assert pyproj == source


def test_pyproject_read_nowrite(tmp_path, testdata):
    # In this test, we read from pyproject.toml but don't update what gets
    # written, so the built sdist will not have a [project] table.
    pyproj, source, pkgconf = build_testpyproject("_msbuild01.py", "1.0.0", tmp_path, testdata)
    assert [l for l in pyproj if l.startswith('[')] \
           == ["[build-system]", "[tool.not-a-real-tool]", "[tool.another-fake-tool]"]
    assert source != pyproj
    assert 'Version: 1.0.0' in pkgconf
    assert 'version=' not in pyproj


def test_pyproject_read_overwrite(tmp_path, testdata):
    # In this test, we read from pyproject.toml, overwrite existing metadata,
    # and update the output.
    pyproj, source, pkgconf = build_testpyproject("_msbuild02.py", "1.0.0", tmp_path, testdata)
    assert [l for l in pyproj if l.startswith('[')] \
           == ["[build-system]", "[tool.not-a-real-tool]", "[tool.another-fake-tool]", "[project]"]
    assert source != pyproj
    print(pyproj)
    assert "Version: 1.0.0" in pkgconf
    assert "version='1.0.0'" in pyproj


def test_pyproject_read_merge(tmp_path, testdata):
    # In this test, we read from pyproject.toml, preserve existing metadata,
    # and update the output.
    pyproj, source, pkgconf = build_testpyproject("_msbuild03.py", "0.0.1", tmp_path, testdata)
    assert [l for l in pyproj if l.startswith('[')] \
           == ["[build-system]", "[tool.not-a-real-tool]", "[tool.another-fake-tool]", "[project]"]
    assert source != pyproj
    print(pyproj)
    assert "Version: 0.0.1" in pkgconf
    assert "version='0.0.1'" in pyproj

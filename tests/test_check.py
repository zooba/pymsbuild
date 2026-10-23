import os
import shutil
import subprocess
import sys

from importlib.machinery import EXTENSION_SUFFIXES
from pathlib import Path, PurePath
from types import SimpleNamespace

import pytest

from pymsbuild._build import BuildState
from pymsbuild._types import File, Package, PydFile, PyFile, SourceFile
from pymsbuild.dllpack import DllPackage


ROOT = Path(__file__).absolute().parent.parent


def run_check(source, *args):
    return subprocess.run(
        [sys.executable, "-m", "pymsbuild", "check", "-s", str(source), *args],
        cwd=source,
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT),
            "PYMSBUILD_VERBOSE": "0",
            "PYMSBUILD_SHOW_TRACEBACKS": "0",
            "PYMSBUILD_CONFIG": "",
            "MSBUILD": "must-not-run-msbuild",
        },
        capture_output=True,
        text=True,
    )


@pytest.fixture
def sample(tmp_path):
    source = tmp_path / "sample"
    shutil.copytree(ROOT / "samples" / "cross-compile", source)
    return source


@pytest.mark.parametrize("project", [
    "samples/cross-compile", "samples/pybind11", "samples/azure-pack",
    pytest.param("samples/azure-cli", marks=pytest.mark.skipif(
        sys.platform not in {"win32", "linux"}, reason="no sample requirements for this platform",
    )),
    "tests/testproject1", "tests/testempty",
])
def test_check_silent(project, tmp_path, monkeypatch, capsys):
    source = tmp_path / "sample"
    shutil.copytree(ROOT / project, source)

    def unexpected(*args, **kwargs):
        pytest.fail("check must not locate, generate, or execute MSBuild")

    monkeypatch.setattr("pymsbuild._build.locate_msbuild", unexpected)
    monkeypatch.setattr("pymsbuild._generate.generate", unexpected)
    monkeypatch.setattr(BuildState, "build", unexpected)
    monkeypatch.delenv("MSBUILD", raising=False)
    monkeypatch.chdir(source)
    state = BuildState()
    state.source_dir = source
    state.check()
    assert capsys.readouterr() == ("", "")
    assert not (source / "build").exists()
    assert not list(source.rglob("*.proj"))
    assert BuildState.current is None


@pytest.mark.parametrize("args, expected", [
    ((), []),
    (("--list-sdist",), [
        "# Sdist files", "_msbuild.py", "empty.py", "native.c", "pyproject.toml",
    ]),
    (("--list-wheel",), [
        "# Wheel files",
        "cross_compile_sample/__init__.py",
        "cross_compile_sample/_native$(DefaultExtSuffix)",
    ]),
    (("--list-sdist", "--list-wheel"), [
        "# Sdist files", "_msbuild.py", "empty.py", "native.c", "pyproject.toml",
        "", "# Wheel files",
        "cross_compile_sample/__init__.py",
        "cross_compile_sample/_native$(DefaultExtSuffix)",
    ]),
])
def test_check_cli(sample, args, expected):
    result = run_check(sample, *args)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout == "".join(
        (str(PurePath(p)) if p and not p.startswith("#") else p) + "\n"
        for p in expected
    )
    assert not (sample / "build").exists()
    assert not list(sample.rglob("*.proj"))


def test_check_expand_cli(sample):
    result = run_check(sample, "--list-wheel", "--expand")
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "$(DefaultExtSuffix)" not in result.stdout
    assert "cross_compile_sample/_native" in result.stdout


def test_check_expands_wildcards_and_properties(tmp_path, capsys):
    source = tmp_path / "source"
    (source / "src" / "pkg" / "sub").mkdir(parents=True)
    (source / "_msbuild.py").write_text("")
    (source / "src" / "pkg" / "a.py").write_text("")
    (source / "src" / "pkg" / "sub" / "b.py").write_text("")
    state = BuildState()
    state.source_dir = source
    state.config = SimpleNamespace(
        METADATA={"Name": "sample", "Version": "1.0"},
        PACKAGE=Package("pkg", PyFile("**/*.py"), PydFile("_native"), source="src/pkg"),
    )

    state.check(list_sdist=True, list_wheel=True, expand=True)
    out, err = capsys.readouterr()
    assert err == ""
    paths = set(out.splitlines())
    native = next(p for p in paths if p.startswith("pkg/_native"))
    assert paths == {
        "# Sdist files", "_msbuild.py", "src/pkg/a.py", "src/pkg/sub/b.py", "",
        "# Wheel files", "pkg/a.py", "pkg/sub/b.py",
    } | {native}
    assert native.endswith(tuple(EXTENSION_SUFFIXES))


@pytest.mark.parametrize("config, message", [
    ("missing.py", "does not exist"),
    ("_msbuild.py", "config failure"),
])
def test_check_failure(sample, config, message):
    if config == "_msbuild.py":
        (sample / config).write_text("raise RuntimeError('config failure')\n")
    result = run_check(sample, "--config", config)
    assert result.returncode == 1
    assert result.stdout == ""
    assert message in result.stderr
    assert not (sample / "build").exists()


def test_check_paths_and_hooks(sample, capsys):
    class CustomMember:
        def iter_sdist(self, source_dir):
            yield source_dir / "custom.input"

        def iter_wheel(self, prefix):
            yield prefix / "custom.output"

    tags = []

    def init_package(tag):
        tags.append(tag)
        return Package(
            "package",
            PyFile("**/*.py"),
            SourceFile("native.c"),
            File("$(Generated)/data.bin", IncludeInSdist=False),
            Package("sub", PyFile("original.py", "__init__.py")),
            PydFile("_native", TargetExt=".pyd"),
            CustomMember(),
            source="src",
        )

    state = BuildState()
    state.source_dir = sample
    state.config = SimpleNamespace(
        METADATA={"Name": "sample", "Version": "1.0"},
        init_PACKAGE=init_package,
    )
    state.check(list_sdist=True, list_wheel=True)
    out, err = capsys.readouterr()
    assert err == ""
    assert out.startswith("# Sdist files\n")
    assert "\n\n# Wheel files\n" in out
    assert {PurePath(p) for p in out.splitlines() if p and not p.startswith("#")} == {
        PurePath(p) for p in {
            "_msbuild.py", "pyproject.toml", "src/**/*.py", "src/native.c",
            "src/original.py", "src/custom.input", "package/**/*.py",
            "package/data.bin", "package/sub/__init__.py",
            "package/_native.pyd", "package/custom.output",
        }
    }
    assert tags[0] is None
    assert tags[1]


def test_dllpackage_wheel_paths():
    package = DllPackage(
        "packed", PyFile("module.py"), File("data.txt"),
        Package("sub", PyFile("module.py")),
        PydFile("_native", TargetExt=".pyd"),
    )
    assert list(package.iter_wheel(PurePath())) == [
        PurePath("packed$(DefaultExtSuffix)"), PurePath("_native.pyd"),
    ]

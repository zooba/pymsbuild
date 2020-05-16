"""The pymsbuild build backend.
"""

__version__ = "0.0.1"

import contextvars
import sys
from pathlib import Path

from pymsbuild import _build
from pymsbuild._types import *

_CONFIG_DIR = contextvars.ContextVar("CONFIG_DIR")
_TEMP_DIR = contextvars.ContextVar("BUILD_DIR")
_DISTINFO = contextvars.ContextVar("DISTINFO", default={})
_PROJECTS = contextvars.ContextVar("PROJECTS", default=[])
_RECORD = contextvars.ContextVar("RECORD")
_BUILD_PROJECT = contextvars.ContextVar("BUILD_PROJECT")


def read_config(root):
    import importlib
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_msbuild",
        root / "_msbuild.py",
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__loader__.exec_module(mod)
    return mod


def generate(config):
    from ._generate import generate as G
    source_dir = Path(config.__file__).parent
    build_dir = source_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    G(config.PACKAGE, build_dir, source_dir)

"""
def _path_globber(p):
    p = Path(p)
    return p.parent.glob(p.name)


def _get_build_state(*, build_dir=None, install_dir=None, msbuild_exe=..., globber=...):
    from pymsbuild._build import BuildState, locate
    if msbuild_exe is ...:
        msbuild_exe = locate()
    if globber is ...:
        globber = _path_globber
    src_dir = _CONFIG_DIR.get(Path.cwd())
    tmp_dir = _TEMP_DIR.get(Path.cwd() / "build")
    return BuildState(
        _DISTINFO.get(),
        src_dir,
        build_dir or (tmp_dir / "lib"),
        tmp_dir / "temp",
        install_dir,
        msbuild_exe,
        globber,
    )


def build_in_place(*, msbuild_exe=..., globber=..., target=...):
    bs = _get_build_state(
        install_dir=_CONFIG_DIR.get(Path.cwd()),
        msbuild_exe=msbuild_exe,
        globber=globber,
    )
    for project in _PROJECTS.get():
        bs.generate(project)
    project = _BUILD_PROJECT.get()
    if target is ...:
        target = "Install"
    bs.build(project, target=target)


# PEP 517 hooks

def build_sdist(sdist_directory, config_settings=None):
    sdist_directory = Path(sdist_directory)
    sdist_directory.mkdir(parents=True, exist_ok=True)
    _TEMP_DIR.set(Path("./build/sdist_temp").absolute())
    bs = _get_build_state(globber=_path_globber)
    import gzip, tarfile
    name, version = bs.distinfo["name"], bs.distinfo["version"]
    sdist = sdist_directory / "{}_{}.tar.gz".format(name, version)
    with gzip.open(sdist, "w") as f_gz:
        with tarfile.TarFile.open(
            sdist.with_suffix(".tar"),
            "w",
            fileobj=f_gz,
            format=tarfile.PAX_FORMAT
        ) as f:
            bs.build_sdist(_BUILD_PROJECT.get(), f.add)
    return name


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    wheel_directory = Path(wheel_directory)
    if metadata_directory is None:
        metadata_directory = wheel_directory / prepare_metadata_for_build_wheel(wheel_directory)
    else:
        metadata_directory = Path(metadata_directory)
    #outdir = wheel_directory / "{name}"


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    metadata_directory = Path(metadata_directory)
    distinfo = _DISTINFO.get()
    outdir = metadata_directory / "{name}-{version}.dist-info".format_map(distinfo)
    outdir.mkdir(parents=True, exist_ok=True)

    _TEMP_DIR.set(_CONFIG_DIR.get(Path.cwd()) / "build")
    bs = _get_build_state()
    bs.install_dir = bs.build_dir
    bs.layout_file = bs.temp_dir / "layout.txt"
    for project in _PROJECTS.get():
        bs.generate(project)
    project = _BUILD_PROJECT.get()
    bs.build(project, target="Build;WriteLayout")

    with open(outdir / "METADATA", "w", encoding="utf-8") as f:
        # TODO: Any metadata
        print(file=f)

    with open(outdir / "WHEEL", "w", encoding="utf-8") as f:
        print("Wheel-Version: 1.0", file=f)
        print("Generator: pymsbuild", __version__, file=f)
        print("Root-Is-Purelib: false", file=f)
        # TODO: Correct tags
        #print("Tag: py3-none-win_amd64", file=f)
        # TODO: Correct build number
        #print("Build: 1", file=f)

    with open(bs.layout_file, "r", encoding="utf-8") as f:
        with open(outdir / "RECORD", "w", encoding="utf-8") as record:
            for line in f:
                src, _, dst = line.strip().partition(";")
                print(dst, file=record)

    return outdir.name
"""
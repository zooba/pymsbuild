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
    return root / "_msbuild.py"


def _path_globber(p):
    p = Path(p)
    return p.parent.glob(p.name)


def _get_build_state(*, install_dir=None, msbuild_exe=..., globber=...):
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
        tmp_dir / "lib",
        tmp_dir / "temp",
        install_dir,
        msbuild_exe,
        globber,
    )


def build_in_place(install_dir, msbuild_exe=..., globber=...):
    bs = _get_build_state(
        install_dir=install_dir,
        msbuild_exe=msbuild_exe,
        globber=globber,
    )
    for project in _PROJECTS.get():
        bs.generate(project)
    project = _BUILD_PROJECT.get()
    bs.build(project)


# PEP 517 hooks

def build_sdist(sdist_directory, config_settings=None):
    sdist_directory = Path(sdist_directory)
    sdist_directory.mkdir(parents=True, exist_ok=True)
    _TEMP_DIR.set(Path("./sdist_temp").absolute())
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
    pass


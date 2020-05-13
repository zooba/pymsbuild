"""The pymsbuild build backend.
"""

__version__ = "0.0.1"

import contextvars
import sys
from pathlib import Path

from pymsbuild import _build
from pymsbuild._types import *

_TEMP_DIR_CV = contextvars.ContextVar("BUILD_DIR")

_TO_BUILD = []


def _build(target):
    _TO_BUILD.append(target)


def get_projects():
    return _TO_BUILD


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


def build_in_place(source_dir, temp_dir):
    from pymsbuild._build import locate, BuildState
    msbuild_exe = locate()
    for target, distinfo in get_projects():
        bs = BuildState(
            distinfo,
            target,
            target._get_sources(source_dir, _path_globber),
            source_dir / target.root,
            temp_dir,
            None,
        )
        bs.build(msbuild_exe)


def build_to_dir(source_dir, temp_dir, build_dir):
    from pymsbuild._build import locate, BuildState
    msbuild_exe = locate()
    for target, distinfo in get_projects():
        bs = BuildState(
            distinfo,
            target,
            target._get_sources(source_dir, _path_globber),
            build_dir,
            temp_dir,
            None,
        )
        bs.build(msbuild_exe)


def list_output(source_dir, output=..., globber=...):
    all_outputs = {}
    if globber is ...:
        globber = _path_globber
    for target in get_projects():
        for kind, src, dst in target._get_sources(source_dir, globber):
            o = all_outputs
            for bit in dst.split(".")[:-1]:
                o = o.setdefault(bit, {})
            o[dst.rpartition(".")[-1]] = src

    def _list(o, p=""):
        for k in sorted(o):
            v = o[k]
            if isinstance(v, dict):
                yield from _list(v, f"{p}{k}\\")
            else:
                yield f"{p}{k}  <-  {v}"

    yield from _list(all_outputs)


# PEP 517 hooks

def build_sdist(sdist_directory, config_settings=None):
    from pymsbuild._build import locate, BuildState
    import tarfile
    sdist_directory = Path(sdist_directory)
    sdist_directory.mkdir(parents=True, exist_ok=True)
    tmp_dir = _TEMP_DIR_CV.get(Path.cwd()) / "build"
    for target, distinfo in get_projects():
        name = f"{distinfo['name']}-{distinfo['version']}.tar.gz"
        sdist = sdist_directory / name
        bs = BuildState(
            distinfo,
            target,
            target._get_sources(Path.cwd(), _path_globber),
            tmp_dir / "temp",
        )
        #bs.layout_sdist(Path.cwd(), sdist_layout)
        with tarfile.TarFile.open(sdist, "w", format=tarfile.PAX_FORMAT) as f:
            bs.build_sdist(Path.cwd(), tmp_dir, f)
        return name


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    pass


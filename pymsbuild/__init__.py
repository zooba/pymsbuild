"""The pymsbuild build backend.
"""

__version__ = "0.0.1"

import contextvars
import os
import packaging.tags
import re
import shutil
import sys
from pathlib import Path

from pymsbuild import _build
from pymsbuild._types import *

DEFAULT_TAG = next(iter(packaging.tags.sys_tags()), "py3-none-any")

_VERBOSE = contextvars.ContextVar("VERBOSE", default=True)

def _log(*values, sep=" "):
    if _VERBOSE.get():
        print(*values, sep=sep)


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


def generate(output_dir, source_dir, build_dir, force=False, config=None, pkginfo=None, **unused):
    if config is None:
        config = read_config(source_dir)
    from ._generate import generate as G, generate_distinfo as GD
    build_dir.mkdir(parents=True, exist_ok=True)
    pkginfo = pkginfo or (source_dir / "PKG-INFO")
    if pkginfo.is_file():
        _log("Using", pkginfo)
        shutil.copy(pkginfo, build_dir / "PKG-INFO")
    else:
        if hasattr(config, "init_METADATA"):
            _log("Dynamically initialising METADATA")
            config.METADATA = config.init_METADATA() or config.METADATA
        if hasattr(config, "METADATA"):
            _log("Generating", build_dir / "PKG-INFO")
            GD(config.METADATA, build_dir, source_dir)
    if hasattr(config, "init_PACKAGE"):
        _log("Dynamically initialising PACKAGE")
        config.PACKAGE = config.init_PACKAGE() or config.PACKAGE
    _log("Generating projects")
    p = G(config.PACKAGE, build_dir, source_dir)
    _log("Generated", p)
    return p


def build(project, *, quiet=False, target="Build", msbuild_exe=None, **properties):
    import subprocess
    project = Path(project)
    msbuild_exe = msbuild_exe or _build.locate()
    _log("Compiling", project, "with", msbuild_exe, "({})".format(target))
    properties.setdefault("Configuration", "Release")
    properties.setdefault("HostPython", sys.executable)
    properties.setdefault("PyMsbuildTargets", Path(__file__).parent / "targets")
    rsp = Path(f"{project}.{os.getpid()}.rsp")
    with rsp.open("w", encoding="utf-8-sig") as f:
        print(project, file=f)
        print("/nologo", file=f)
        if _VERBOSE.get():
            print("/p:_Low=Normal", file=f)
        print("/v:n", file=f)
        print("/t:", target, sep="", file=f)
        for k, v in properties.items():
            if v is None:
                continue
            if k in {"IntDir", "OutDir", "SourceDir"}:
                v = str(v).replace("/", "\\")
                if not v.endswith("\\"):
                    v += "\\"
            print("/p:", k, "=", v, sep="", file=f)
    if _VERBOSE.get():
        with rsp.open("r", encoding="utf-8-sig") as f:
            _log(" ".join(map(str.strip, f)))
        _log()
    _run = subprocess.check_output if quiet else subprocess.check_call
    try:
        _run([msbuild_exe, "/noAutoResponse", f"@{rsp}"],
             stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as ex:
        if quiet:
            print(ex.stdout.decode("mbcs", "replace"))
        sys.exit(1)
    else:
        rsp.unlink()


def build_in_place(output_dir, **kwargs):
    _VERBOSE.set(kwargs.pop("verbose", _VERBOSE.get()))
    p = generate(output_dir, **kwargs)
    build(p, target="BuildInPlace")


def clean(output_dir, **kwargs):
    _VERBOSE.set(kwargs.pop("verbose", _VERBOSE.get()))
    config = kwargs.get("config") or read_config(kwargs["source_dir"])
    proj = kwargs["build_dir"] / (config.PACKAGE.name + ".proj")
    if proj.is_file():
        build(proj, target="Clean")


def build_sdist(sdist_directory, config_settings=None, **kwargs):
    _VERBOSE.set(kwargs.pop("verbose", _VERBOSE.get()))
    sdist_directory = Path(sdist_directory)
    sdist_directory.mkdir(parents=True, exist_ok=True)
    config = kwargs.get("config") or read_config(kwargs["source_dir"])
    target = "RebuildSdist" if kwargs.get("force", False) else "BuildSdist"
    root_dir = kwargs.get("build_dir") or (Path.cwd() / "build")
    build_dir = root_dir / "sdist"
    temp_dir = root_dir / "temp"
    p = generate(sdist_directory, **kwargs)
    build(
        p,
        target=target,
        OutDir=build_dir,
        IntDir=temp_dir,
    )
    return pack_sdist(sdist_directory, build_dir, config=config)


def pack_sdist(output_dir, build_dir, **kwargs):
    _VERBOSE.set(kwargs.pop("verbose", _VERBOSE.get()))
    import gzip, tarfile
    config = kwargs.get("config") or read_config(kwargs["source_dir"])
    name, version = config.METADATA["Name"], config.METADATA["Version"]
    sdist = output_dir / "{}-{}.tar.gz".format(name, version)
    with gzip.open(sdist, "w") as f_gz:
        with tarfile.TarFile.open(
            sdist.with_suffix(".tar"),
            "w",
            fileobj=f_gz,
            format=tarfile.PAX_FORMAT
        ) as f:
            f.add(build_dir, arcname="{}-{}".format(name, version), recursive=True)
    return sdist.name


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None, **kwargs):
    _VERBOSE.set(kwargs.pop("verbose", _VERBOSE.get()))
    config = kwargs.get("config") or read_config(kwargs["source_dir"])
    kwargs.setdefault("config", config)
    source_dir = Path(config.__file__).absolute().parent
    name, version = config.METADATA["Name"], config.METADATA["Version"]
    wheel_directory = Path(wheel_directory)

    root_dir = kwargs.setdefault("build_dir", Path.cwd() / "build")
    build_dir = root_dir / "wheel"
    shutil.rmtree(build_dir)
    temp_dir = root_dir / "temp"
    if metadata_directory is None:
        metadata_directory = build_dir
        prepare_metadata_for_build_wheel(build_dir, config_settings, **kwargs)
    else:
        metadata_directory = Path(metadata_directory)
    p = generate(
        build_dir, source_dir, temp_dir, config=config,
        pkginfo=metadata_directory / "PKG-INFO",
    )
    target = "Rebuild" if kwargs.get("force", False) else "Build"
    build(p, target=target, OutDir=build_dir, IntDir=temp_dir)

    tag = config.METADATA.get("WheelTag") or DEFAULT_TAG
    wheel = wheel_directory / "{}-{}-{}.whl".format(
        re.sub("[^\w\d.]+", "_", name, re.UNICODE),
        re.sub("[^\w\d.]+", "_", version, re.UNICODE),
        re.sub("[^\w\d.]+", "_", tag, re.UNICODE),
    )
    pack_wheel(wheel, build_dir, metadata_directory, source_dir)
    return wheel.name


def pack_wheel(wheel, build_dir, metadata_directory, source_dir, **kwargs):
    _VERBOSE.set(kwargs.pop("verbose", _VERBOSE.get()))
    config = kwargs.get("config") or read_config(source_dir)
    name, version = config.METADATA["Name"], config.METADATA["Version"]
    import zipfile
    wheel = Path(wheel)
    wheel.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as f:
        if metadata_directory != build_dir:
            for n in metadata_directory.rglob(r"**\*"):
                f.write(n, n.relative_to(metadata_directory))
        for n in build_dir.rglob(r"**\*"):
            f.write(n, n.relative_to(build_dir))


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None, **kwargs):
    _VERBOSE.set(kwargs.pop("verbose", _VERBOSE.get()))
    config = kwargs.get("config") or read_config(kwargs["source_dir"])
    name, version = config.METADATA["Name"], config.METADATA["Version"]
    tag = config.METADATA.get("WheelTag") or DEFAULT_TAG
    metadata_directory = Path(metadata_directory)
    outdir = metadata_directory / "{}-{}.dist-info".format(name, version)
    outdir.mkdir(parents=True, exist_ok=True)

    root_dir = kwargs.setdefault("build_dir", Path.cwd() / "build")
    build_dir = root_dir / "wheel"
    temp_dir = root_dir / "temp"
    generate(build_dir, Path.cwd(), temp_dir, force=False, config=config)

    with open(outdir / "WHEEL", "w", encoding="utf-8") as f:
        print("Wheel-Version: 1.0", file=f)
        print("Generator: pymsbuild", __version__, file=f)
        print("Root-Is-Purelib: false", file=f)
        for t in sorted(packaging.tags.parse_tag(tag)):
            print("Tag:", t, file=f)
        if os.getenv("BUILD_BUILDNUMBER"):
            print("Build:", os.getenv("BUILD_BUILDNUMBER", "0"), file=f)

    shutil.copy(temp_dir / "PKG-INFO", outdir / "METADATA")

    return outdir.name
"""The pymsbuild build backend.
"""

__version__ = "0.0.1"

import contextvars
import os
import packaging.tags
import re
import shutil
import subprocess
import sys
from pathlib import Path

from pymsbuild import _build
from pymsbuild._types import *

_TAG_PLATFORM_MAP = {
    "win32": "Win32",
    "win_amd64": "x64",
    "win_arm64": "ARM64",
    "any": None,
}


def _add_and_record(zipfile, path, relpath, hashalg="sha256"):
    import base64, hashlib
    hasher = getattr(hashlib, hashalg)() if hashalg else None
    l = 0
    with open(path, "rb") as f:
        with zipfile.open(str(relpath), "w") as zf:
            for b in iter(lambda: f.read(8192), b""):
                if hasher:
                    hasher.update(b)
                l += len(b)
                zf.write(b)
    if hashalg:
        return "{},{}={},{}".format(
            relpath,
            hashalg,
            base64.urlsafe_b64encode(hasher.digest()).rstrip(b"=").decode(),
            l,
        )
    return "{},,".format(relpath)


class BuildState:
    def __init__(self):
        self.verbose = False
        self.quiet = False
        self.force = False
        self._config = None
        self.package = None
        self.metadata = None
        self.project = None
        self.target = None
        for t in packaging.tags.sys_tags():
            self.wheel_tag = str(t)
            break
        else:
            self.wheel_tag = "py3-none-any"

        self._msbuild_exe = None
        self.source_dir = Path.cwd()
        self.config_file = None
        self.output_dir = self.source_dir / "dist"
        self.build_dir = self.source_dir / "build" / "layout"
        self.temp_dir = self.source_dir / "build" / "temp"
        self.pkginfo = self.source_dir / "PKG-INFO"
        self.targets = Path(__file__).parent / "targets"

    @property
    def config(self):
        if self._config is None:
            import importlib
            import importlib.util
            file = self.source_dir / (self.config_file or "_msbuild.py")
            spec = importlib.util.spec_from_file_location("_msbuild", file)
            self._config = mod = importlib.util.module_from_spec(spec)
            mod.__loader__.exec_module(mod)
        return self._config

    @property
    def msbuild_exe(self):
        if self._msbuild_exe is None:
            from ._build import locate
            self._msbuild_exe = locate()
        return self._msbuild_exe

    @msbuild_exe.setter
    def msbuild_exe(self, value):
        self._msbuild_exe = Path(value)

    def log(self, *values, sep=" "):
        if self.verbose:
            print(*values, sep=sep)

    def write(self, *values, sep=" "):
        if not self.quiet:
            print(*values, sep=sep)

    def generate(self):
        from . import _generate as G
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        if self.metadata is None:
            if self.pkginfo.is_file():
                self.log("Using", self.pkginfo)
                self.metadata = G.readback_distinfo(self.pkginfo)
            else:
                if hasattr(self.config, "init_METADATA"):
                    self.log("Dynamically initialising METADATA")
                    self.metadata = self.config.init_METADATA()
                    if self.metadata:
                        self.config.METADATA = self.metadata
                    else:
                        self.metadata = self.config.METADATA
                if hasattr(self.config, "METADATA"):
                    self.metadata = self.config.METADATA
        if self.metadata is not None:
            self.pkginfo = self.temp_dir / "PKG-INFO"
            self.log("Generating", self.pkginfo)
            G.generate_distinfo(self.metadata, self.temp_dir, self.source_dir)
        self.wheel_tag = self.metadata.get("WheelTag", self.wheel_tag)

        if self.package is None:
            if hasattr(self.config, "init_PACKAGE"):
                self.log("Dynamically initialising PACKAGE")
                pack = self.config.init_PACKAGE(str(self.wheel_tag))
                if pack:
                    self.config.PACKAGE = self.package
            self.package = self.config.PACKAGE

        if self.project is None:
            self.log("Generating projects")
            self.project = Path(G.generate(
                self.package,
                self.temp_dir,
                self.source_dir,
                self.config_file,
            ))
            self.log("Generated", self.project)

        return self.project

    def build(self, **properties):
        if self.target is None:
            self.target = "Rebuild" if self.force else "Build"
        self.log("Compiling", self.project, "with", self.msbuild_exe, "({})".format(self.target))
        properties.setdefault("Configuration", "Release")
        for tag in packaging.tags.parse_tag(self.wheel_tag):
            properties.setdefault("Platform", _TAG_PLATFORM_MAP.get(tag.platform))
            break
        properties.setdefault("HostPython", sys.executable)
        properties.setdefault("PyMsbuildTargets", self.targets)
        properties.setdefault("_ProjectBuildTarget", self.target)
        properties.setdefault("OutDir", self.build_dir)
        properties.setdefault("IntDir", self.temp_dir)
        rsp = Path(f"{self.project}.{os.getpid()}.rsp")
        with rsp.open("w", encoding="utf-8-sig") as f:
            print(self.project, file=f)
            print("/nologo", file=f)
            if self.verbose:
                print("/p:_Low=Normal", file=f)
                print("/v:n", file=f)
            else:
                print("/v:m", file=f)
            print("/t:", self.target, sep="", file=f)
            for k, v in properties.items():
                if v is None:
                    continue
                if k in {"IntDir", "OutDir", "SourceDir"}:
                    v = str(v).replace("/", "\\")
                    if not v.endswith("\\"):
                        v += "\\"
                print("/p:", k, "=", v, sep="", file=f)
        if self.verbose:
            with rsp.open("r", encoding="utf-8-sig") as f:
                self.log(" ".join(map(str.strip, f)))
            self.log()
        _run = subprocess.check_output if self.quiet else subprocess.check_call
        try:
            _run([str(self.msbuild_exe), "/noAutoResponse", f"@{rsp}"],
                 stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as ex:
            if self.quiet:
                print(ex.stdout.decode("mbcs", "replace"))
            sys.exit(1)
        else:
            rsp.unlink()

    def build_in_place(self):
        self.generate()
        assert self.project
        self.target = "RebuildInPlace" if self.force else "BuildInPlace"
        self.build()

    def clean(self):
        p = self.config.PACKAGE
        self.project = self.temp_dir / (p.name + ".proj")
        if self.project.is_file():
            self.target = "Clean"
            self.build()

    def build_sdist(self):
        self.target = "RebuildSdist" if self.force else "BuildSdist"
        if self.build_dir.is_dir():
            shutil.rmtree(self.build_dir)
            self.build_dir.mkdir(parents=True, exist_ok=True)
        self.generate()
        self.build()
        return self.pack_sdist()

    def pack_sdist(self):
        import gzip, tarfile
        self.output_dir.mkdir(parents=True, exist_ok=True)
        name, version = self.metadata["Name"], self.metadata["Version"]
        sdist_basename = "{}-{}".format(
            re.sub(r"[^\w\d.]+", "_", name, re.UNICODE),
            re.sub(r"[^\w\d.]+", "_", version, re.UNICODE),
        )
        sdist = (self.output_dir / sdist_basename).with_suffix(".tar.gz")
        with gzip.open(sdist, "w") as f_gz:
            with tarfile.TarFile.open(
                sdist_basename + ".tar",
                "w",
                fileobj=f_gz,
                format=tarfile.PAX_FORMAT
            ) as f:
                f.add(
                    self.build_dir,
                    arcname=sdist_basename,
                    recursive=True,
                )
        self.write("Wrote sdist to", sdist)
        return sdist.name

    def build_wheel(self, metadata_dir=None):
        self.target = "Rebuild" if self.force else "Build"
        if self.build_dir.is_dir():
            shutil.rmtree(self.build_dir)
        if metadata_dir is None:
            metadata_dir = self.temp_dir / "metadata"
            if metadata_dir.is_dir():
                shutil.rmtree(metadata_dir)
        else:
            metadata_dir = Path(metadata_dir)

        self.generate()
        if not metadata_dir.is_dir():
            self.prepare_wheel_distinfo(metadata_dir)

        self.build()
        return self.pack_wheel(metadata_dir)

    def pack_wheel(self, metadata_dir):
        import hashlib, zipfile
        self.output_dir.mkdir(parents=True, exist_ok=True)

        name, version = self.metadata["Name"], self.metadata["Version"]
        wheel = self.output_dir / "{}-{}-{}.whl".format(
            re.sub(r"[^\w\d.]+", "_", name, re.UNICODE),
            re.sub(r"[^\w\d.]+", "_", version, re.UNICODE),
            self.wheel_tag,
        )
        record = []
        with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as f:
            for n in metadata_dir.rglob(r"**\*"):
                if n.is_file():
                    record.append(_add_and_record(f, n, n.relative_to(metadata_dir)))
            for n in self.build_dir.rglob(r"**\*"):
                if n.is_file():
                    record.append(_add_and_record(f, n, n.relative_to(self.build_dir)))
            record_files = []
            for n in metadata_dir.glob("*.dist-info"):
                if not n.is_dir():
                    continue
                record_files.append(r"{}\RECORD".format(n.name))
                record.append(r"{}\RECORD,,".format(n.name))
            record_file = "\n".join(record).encode("utf-8")
            for n in record_files:
                f.writestr(n, record_file)
        self.write("Wrote wheel to", wheel)
        return wheel.name

    def prepare_wheel_distinfo(self, metadata_dir=None):
        metadata_dir = Path(metadata_dir or self.output_dir)
        self.generate()
        name, version = self.metadata["Name"], self.metadata["Version"]
        outdir = metadata_dir / "{}-{}.dist-info".format(
            re.sub(r"[^\w\d.]+", "_", name, re.UNICODE),
            re.sub(r"[^\w\d.]+", "_", version, re.UNICODE),
        )
        outdir.mkdir(parents=True, exist_ok=True)
        with open(outdir / "WHEEL", "w", encoding="utf-8") as f:
            print("Wheel-Version: 1.0", file=f)
            print("Generator: pymsbuild", __version__, file=f)
            print("Root-Is-Purelib: false", file=f)
            for t in sorted(self.wheel_tag):
                print("Tag:", t, file=f)
            if os.getenv("BUILD_BUILDNUMBER"):
                print("Build:", os.getenv("BUILD_BUILDNUMBER", "0"), file=f)
        shutil.copy(self.pkginfo, outdir / "METADATA")
        return outdir.name


def build_sdist(sdist_directory, config_settings=None):
    bs = BuildState()
    bs.output_dir = Path(sdist_directory)
    return bs.build_sdist()


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    bs = BuildState()
    bs.output_dir = Path(wheel_directory)
    return bs.build_wheel()


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    bs = BuildState()
    bs.output_dir = Path(metadata_directory)
    return bs.prepare_wheel_distinfo(bs.output_dir)

import os
import packaging.tags
import re
import shutil
import subprocess
import sys
import sysconfig

from pathlib import PurePath, Path

from . import _generate

if sys.platform == "win32":
    _WINDOWS = True
    from ._locate_vs import locate_msbuild
else:
    _WINDOWS = False
    from ._locate_dotnet import locate_msbuild


# Needed to avoid printing an unhelpful message every time we invoke dotnet
os.environ["DOTNET_NOLOGO"] = "1"


class TagPlatformMap(dict):
    def __missing__(self, key):
        if re.match(r"manylinux.+x86_64", key):
            return "POSIX_x64"
        raise KeyError(f"Unsupported platform '{key}'")

_TAG_PLATFORM_MAP = TagPlatformMap({
    "win32": "Win32",
    "win_amd64": "x64",
    "win_arm": "ARM",
    "win_arm64": "ARM64",
    "linux_x86_64": "POSIX_x64",
    "macosx_10_15_x86_64": "POSIX_x64",
    "any": None,
})


_REMAP_ABI_TO_EXT = {
    "cp37m-win32": "cp37-win32",
    "cp37m-win_amd64": "cp37-win_amd64",
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


def _quote(s, start='"', end='"'):
    if end and s.endswith("\\"):
        end = "\\" + end
    return start + s + end


class BuildState:
    def __init__(self, output_dir=None):
        self._finalized = False
        self.verbose = False
        self.quiet = False
        self.force = False
        self.config = None
        self.package = None
        self.metadata = None
        self.project = None
        self.configuration = None
        self.target = None
        self.msbuild_exe = None
        self.output_dir = Path(output_dir) if output_dir else None
        self.build_dir = None
        self.temp_dir = None
        self.layout_dir = None
        self.layout_extra_files = []
        self.pkginfo = None
        self.source_dir = Path.cwd()
        self.config_file = None
        self.targets = Path(__file__).absolute().parent / "targets"
        self.wheel_tag = None
        self.abi_tag = None
        self.ext_suffix = None
        self.platform = None
        self.build_number = None
        self.python_cflags = None
        self.python_ldflags = None
        self.python_includes = None
        self.python_libs = None

    def finalize(self, getenv=os.getenv):
        if self._finalized:
            return
        self._finalized = True

        self.output_dir = self.source_dir / (self.output_dir or "dist")
        self.build_dir = self.source_dir / (self.build_dir or "build/layout")
        self.temp_dir = self.source_dir / (self.temp_dir or "build/temp")
        self.pkginfo = self.source_dir / (self.pkginfo or "PKG-INFO")

        self._set_best("config_file", None, "PYMSBUILD_CONFIG", "_msbuild.py", getenv)

        if self.config is None:
            import importlib.util
            file = self.source_dir / (self.config_file or "_msbuild.py")
            spec = importlib.util.spec_from_file_location("_msbuild", file)
            self.config = mod = importlib.util.module_from_spec(spec)
            mod.__loader__.exec_module(mod)

        if self.metadata is None:
            if self.pkginfo.is_file():
                self.log("Using", self.pkginfo)
                self.metadata = _generate.readback_distinfo(self.pkginfo)
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

        self._set_best("msbuild_exe", None, "MSBUILD", None, getenv)
        if self.msbuild_exe is None:
            self.msbuild_exe = locate_msbuild()
        if isinstance(self.msbuild_exe, str):
            if Path(self.msbuild_exe).is_file():
                self.msbuild_exe = [self.msbuild_exe]
            else:
                import shlex
                self.msbuild_exe = shlex.split(self.msbuild_exe)

        self._set_best("build_number", None, "BUILD_BUILDNUMBER", None, getenv)

        ext = sysconfig.get_config_var("EXT_SUFFIX")
        default_wheel_tag = str(next(iter(packaging.tags.sys_tags()), None) or "py3-none-any")
        default_abi_tag = ext.rpartition(".")[0].strip(".")
        default_ext_suffix = "".join(ext.rpartition(".")[1:])
        self._set_best("wheel_tag", "WheelTag", "PYMSBUILD_WHEEL_TAG", default_wheel_tag, getenv)
        self._set_best("abi_tag", "AbiTag", "PYMSBUILD_ABI_TAG", default_abi_tag, getenv)
        self._set_best("ext_suffix", "ExtSuffix", "PYMSBUILD_EXT_SUFFIX", default_ext_suffix, getenv)

        p = getattr(next(iter(packaging.tags.parse_tag(self.wheel_tag)), None), "platform", None)
        self._set_best("platform", None, "PYMSBUILD_PLATFORM", p, getenv)
        self._set_best("configuration", None, "PYMSBUILD_CONFIGURATION", "Release", getenv)

        self._set_best("python_config", None, "PYTHON_CONFIG", None, getenv)
        self._set_best("python_includes", None, "PYTHON_INCLUDES", None, getenv)
        self._set_best("python_libs", None, "PYTHON_LIBS", None, getenv)

        if not self.python_includes:
            self.python_includes = sysconfig.get_config_var("INCLUDEPY")
        if not self.python_libs:
            if _WINDOWS:
                self.python_libs = PurePath(sysconfig.get_config_var("installed_base")) / "libs"
            else:
                self.python_libs = sysconfig.get_config_var("LIBPL")

        if self.package is None:
            if hasattr(self.config, "init_PACKAGE"):
                self.log("Dynamically initialising PACKAGE")
                pack = self.config.init_PACKAGE(str(self.wheel_tag))
                if pack:
                    self.config.PACKAGE = self.package
            self.package = self.config.PACKAGE

    def _set_best(self, key, metakey, envkey, default, getenv):
        if getattr(self, key, None):
            self.log("Build state property", key, "already set to", getattr(self, key))
            return
        if metakey:
            v = self.metadata.get(metakey, None)
            if v:
                setattr(self, key, v)
                self.log("Build state property", key, "set to", v, "from metadata item", metakey)
                return
        if envkey:
            v = getenv(envkey)
            if v:
                setattr(self, key, v)
                self.log("Build state property", key, "set to", v, "from environment", envkey)
                return
        setattr(self, key, default)
        if default:
            self.log("Build state property", key, "set to default value", default)

    def log(self, *values, sep=" "):
        if self.verbose:
            print(*values, sep=sep)

    def write(self, *values, sep=" "):
        if not self.quiet:
            print(*values, sep=sep)

    def generate(self):
        if self.project:
            return self.project

        self.finalize()

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        if self.metadata is not None:
            self.pkginfo = self.temp_dir / "PKG-INFO"
            self.log("Generating", self.pkginfo)
            _generate.generate_distinfo(self.metadata, self.temp_dir, self.source_dir)

        ext = f".{self.ext_suffix}"
        if self.abi_tag:
            ext = ".{}.{}".format(
                _REMAP_ABI_TO_EXT.get(self.abi_tag, self.abi_tag),
                self.ext_suffix
            )
        self.log("Setting missing TargetExt to", ext)

        from . import _types as T
        for p in self.package:
            if isinstance(p, T.PydFile):
                p.options["TargetExt"] = p.options.get("TargetExt") or ext

        self.log("Generating projects")
        self.project = Path(_generate.generate(
            self.package,
            self.temp_dir,
            self.source_dir,
            self.config_file,
        ))
        self.log("Generated", self.project)

        return self.project

    def build(self, **properties):
        self.finalize()
        project = self.generate()
        if self.target is None:
            self.target = "Rebuild" if self.force else "Build"
        self.log("Compiling", project, "with", *self.msbuild_exe, "({})".format(self.target))
        if not project.is_file():
            raise FileNotFoundError(project)
        properties.setdefault("Configuration", self.configuration)
        if not properties.get("Platform"):
            try:
                properties["Platform"] = _TAG_PLATFORM_MAP[self.platform]
            except KeyError:
                self.write("WARNING:", self.platform, "is not a known platform. Projects may not compile")
                properties["Platform"] = self.platform
        properties.setdefault("HostPython", sys.executable)
        properties.setdefault("PyMsbuildTargets", self.targets)
        properties.setdefault("_ProjectBuildTarget", self.target)
        properties.setdefault("SourceRootDir", self.source_dir)
        properties.setdefault("OutDir", self.build_dir)
        properties.setdefault("IntDir", self.temp_dir)
        properties.setdefault("PythonConfig", self.python_config)
        properties.setdefault("PythonIncludes", self.python_includes)
        properties.setdefault("PythonLibs", self.python_libs)
        rsp = self.temp_dir / f"{project}.{os.getpid()}.rsp"
        with rsp.open("w", encoding="utf-8-sig") as f:
            print(project, file=f)
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
                    v = f"{PurePath(v)}{os.path.sep}"
                print(_quote(f"/p:{k}={v}"), file=f)
        if self.verbose:
            with rsp.open("r", encoding="utf-8-sig") as f:
                self.log(" ".join(map(str.strip, f)))
            self.log()
        _run = subprocess.check_output if self.quiet else subprocess.check_call
        try:
            _run([*self.msbuild_exe, f"@{rsp}"], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as ex:
            if self.quiet:
                if _WINDOWS:
                    print(ex.stdout.decode("mbcs", "replace"))
                else:
                    print(ex.stdout.decode("utf-8", "replace"))
            sys.exit(1)
        else:
            try:
                rsp.unlink()
            except OSError:
                pass

    def build_in_place(self):
        self.finalize()
        self.generate()
        assert self.project
        self.target = "RebuildInPlace" if self.force else "BuildInPlace"
        self.build()

    def clean(self):
        self.finalize()
        p = self.config.PACKAGE
        self.project = self.temp_dir / (p.name + ".proj")
        if self.project.is_file():
            self.target = "Clean"
            self.build()

    def build_sdist(self):
        self.finalize()
        self.target = "RebuildSdist" if self.force else "BuildSdist"
        if self.build_dir.is_dir():
            shutil.rmtree(self.build_dir)
            self.build_dir.mkdir(parents=True, exist_ok=True)
        self.generate()
        self.build()
        if self.layout_dir:
            return self.layout_sdist()
        return self.pack_sdist()

    def pack_sdist(self):
        self.finalize()
        import gzip, tarfile
        self.output_dir.mkdir(parents=True, exist_ok=True)
        name, version = self.metadata["Name"], self.metadata["Version"]
        sdist_basename = "{}-{}".format(
            re.sub(r"[^\w\d.]+", "_", name, re.UNICODE),
            re.sub(r"[^\w\d.]+", "_", version, re.UNICODE),
        )
        sdist = self.output_dir / (sdist_basename + ".tar.gz")
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
        self.finalize()
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
        if self.layout_dir:
            return self.layout_wheel(metadata_dir)
        return self.pack_wheel(metadata_dir)

    def pack_wheel(self, metadata_dir):
        self.finalize()
        import zipfile
        self.output_dir.mkdir(parents=True, exist_ok=True)

        name, version = self.metadata["Name"], self.metadata["Version"]
        wheel = self.output_dir / "{}-{}-{}.whl".format(
            re.sub(r"[^\w\d.]+", "_", name, re.UNICODE),
            re.sub(r"[^\w\d.]+", "_", version, re.UNICODE),
            self.wheel_tag,
        )
        record = []
        with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as f:
            for n in metadata_dir.rglob(r"**/*"):
                if n.is_file():
                    record.append(_add_and_record(f, n, n.relative_to(metadata_dir)))
            for n in self.build_dir.rglob(r"**/*"):
                if n.is_file():
                    record.append(_add_and_record(f, n, n.relative_to(self.build_dir)))
            record_files = []
            for n in metadata_dir.glob("*.dist-info"):
                if not n.is_dir():
                    continue
                record_files.append(r"{}/RECORD".format(n.name))
                record.append(r"{}/RECORD,,".format(n.name))
            record_file = "\n".join(record).encode("utf-8")
            for n in record_files:
                f.writestr(n, record_file)
        self.write("Wrote wheel to", wheel)
        return wheel.name

    def prepare_wheel_distinfo(self, metadata_dir=None):
        self.finalize()
        metadata_dir = Path(metadata_dir or self.output_dir)
        self.generate()
        name, version = self.metadata["Name"], self.metadata["Version"]
        outdir = metadata_dir / "{}-{}.dist-info".format(
            re.sub(r"[^\w\d.]+", "_", name, re.UNICODE),
            re.sub(r"[^\w\d.]+", "_", version, re.UNICODE),
        )
        outdir.mkdir(parents=True, exist_ok=True)
        from pymsbuild import __version__
        with open(outdir / "WHEEL", "w", encoding="utf-8") as f:
            print("Wheel-Version: 1.0", file=f)
            print("Generator: pymsbuild", __version__, file=f)
            print("Root-Is-Purelib: false", file=f)
            for t in sorted(self.wheel_tag):
                print("Tag:", t, file=f)
            if self.build_number:
                print("Build:", self.build_number, file=f)
        shutil.copy(self.pkginfo, outdir / "METADATA")
        return outdir.name

    def _write_state(self, state_file, outfile, outfmt):
        print("output-format=", outfmt, sep="", file=state_file)
        print("output-file=", outfile, sep="", file=state_file)
        for k in dir(self):
            if not k.startswith("_") and not hasattr(type(self), k):
                v = getattr(self, k)
                if isinstance(v, (str, PurePath)):
                    print(k, "=", getattr(self, k), sep="", file=state_file)
        print("# BEGIN FILES", file=state_file)

    def layout_sdist(self):
        self.finalize()
        import zipfile
        root = Path(self.layout_dir).absolute()
        assert root
        try:
            shutil.rmtree(root)
        except OSError:
            pass
        root.mkdir(parents=True, exist_ok=True)

        name, version = self.metadata["Name"], self.metadata["Version"]
        sdist_basename = "{}-{}".format(
            re.sub(r"[^\w\d.]+", "_", name, re.UNICODE),
            re.sub(r"[^\w\d.]+", "_", version, re.UNICODE),
        )
        sdist = self.output_dir / (sdist_basename + ".tar.gz")
        with (root / "__state.txt").open("w", encoding="utf-8") as f:
            self._write_state(f, sdist, "targz")
            for n in self.build_dir.rglob("**/*"):
                if n.is_file():
                    rn = root / n.relative_to(self.build_dir)
                    rn.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(n, rn)
                    print(rn, file=f)
        self.write("Wrote layout to", root)
        return sdist.name

    def layout_wheel(self, metadata_dir):
        self.finalize()
        import zipfile
        root = Path(self.layout_dir).absolute()
        assert root
        try:
            shutil.rmtree(root)
        except OSError:
            pass
        root.mkdir(parents=True, exist_ok=True)

        name, version = self.metadata["Name"], self.metadata["Version"]
        wheel = self.output_dir / "{}-{}-{}.whl".format(
            re.sub(r"[^\w\d.]+", "_", name, re.UNICODE),
            re.sub(r"[^\w\d.]+", "_", version, re.UNICODE),
            self.wheel_tag,
        )
        with (root / "__state.txt").open("w", encoding="utf-8") as f:
            self._write_state(f, wheel, "whl")
            for n in metadata_dir.rglob("**/*"):
                if n.is_file():
                    rn = root / n.relative_to(metadata_dir)
                    rn.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(n, rn)
                    print(rn, file=f)
            for n in self.build_dir.rglob("**/*"):
                if n.is_file():
                    rn = root / n.relative_to(self.build_dir)
                    rn.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(n, rn)
                    print(rn, file=f)
        self.write("Wrote layout to", root)
        return wheel.name

    def pack(self):
        root = Path(self.layout_dir)
        if not root:
            print(
                "'--layout-dir' argument is required when invoking the 'pack' command",
                file=sys.stderr
            )
            return
        root = root.absolute()
        outfile = None
        outfmt = None
        with (root / "__state.txt").open("r", encoding="utf-8-sig") as f:
            for i in f:
                k, sep, v = i.strip().partition("=")
                if not sep:
                    break
                if k == "output-file":
                    outfile = Path(v)
                elif k == "output-format":
                    outfmt = v
                elif not k.startswith("_") and hasattr(self, k) and not hasattr(type(self), k):
                    setattr(self, k, v)
                else:
                    self.log("Property", k, "from layout directory is ignored")
            files = [root / i.strip() for i in f if i.strip()]
            extra = list(self.layout_extra_files or ())
            seen = set()
            while extra:
                i = (extra.pop(0) or "").strip()
                if i in seen:
                    continue
                seen.add(i)
                if i.startswith("@"):
                    with Path(i[1:]).open("r", encoding="utf-8-sig") as f2:
                        extra.extend(f2)
                elif i:
                    files.append(root / i)
        if not outfmt or not outfile:
            print("Layout appears to be corrupted. Please rerun the first stage again.", file=sys.stderr)
            return
        if outfmt == "targz":
            import gzip, tarfile
            outfile.parent.mkdir(parents=True, exist_ok=True)
            self.log("Writing .tar.gz to", outfile)
            with gzip.open(outfile, "w") as f_gz:
                with tarfile.TarFile.open(
                    PurePath(outfile).with_suffix(""),
                    "w",
                    fileobj=f_gz,
                    format=tarfile.PAX_FORMAT
                ) as f:
                    for n in files:
                        if n.is_file():
                            try:
                                rn = n.relative_to(root)
                            except ValueError:
                                self.write("Not including", n, "from outside of layout directory")
                            else:
                                self.log("Adding", rn)
                                f.add(n, arcname=rn)
            self.write("Wrote sdist to", outfile)
        elif outfmt == "whl":
            import zipfile
            record = []
            record_files = []
            outfile.parent.mkdir(parents=True, exist_ok=True)
            self.log("Writing .whl to", outfile)
            with zipfile.ZipFile(outfile, "w", compression=zipfile.ZIP_DEFLATED) as f:
                for n in files:
                    if n.is_file():
                        try:
                            rn = n.relative_to(root)
                        except ValueError:
                            self.write("Not including", n, "from outside of layout directory")
                        else:
                            self.log("Adding", rn)
                            record.append(_add_and_record(f, n, rn))
                    if n.match("*.dist-info/*"):
                        n2 = "{}{}RECORD".format(n.parent.name, os.path.sep)
                        if n2 not in record_files:
                            record_files.append(n2)
                            record.append("{},,".format(n2))
                record_file = "\n".join(record).encode("utf-8")
                for n in record_files:
                    f.writestr(n, record_file)
            self.write("Wrote wheel to", outfile)
        else:
            print(
                "Unsupported output format '{}'. Please do not modify the state file".format(
                    outfmt,
                ),
                file=sys.stderr,
            )

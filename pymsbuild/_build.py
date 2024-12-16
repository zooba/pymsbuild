import os
import packaging.tags
import re
import shutil
import subprocess
import sys
import sysconfig

from pathlib import PurePath, Path

from . import _generate
from . import _tags

if sys.platform == "win32":
    _WINDOWS = True
    from ._locate_vs import locate_msbuild
else:
    _WINDOWS = False
    from ._locate_dotnet import locate_msbuild


# Needed to avoid printing an unhelpful message every time we invoke dotnet
os.environ["DOTNET_NOLOGO"] = "1"


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


def _relative_to_layout(files, root):
    if not files:
        files = root.rglob("**/*")
    for n in files:
        n = root / n
        try:
            rn = n.relative_to(root)
        except ValueError:
            self.write("Not including", n, "from outside of layout directory")
            continue
        if n.is_file():
            yield n, rn


def _quote(s, start='"', end='"'):
    if end and s.endswith("\\"):
        end = "\\" + end
    return start + s + end


class BuildState:
    # Updated around init_METADATA and init_PACKAGE calls
    current = None

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
        if os.getenv("PYMSBUILD_TEMP_DIR"):
            root_dir = Path(os.getenv("PYMSBUILD_TEMP_DIR"))
            self.build_dir = root_dir / "bin"
            self.temp_dir = root_dir / "temp"
        else:
            self.build_dir = None
            self.temp_dir = None
        self._perform_layout = None
        self.layout_dir = None
        self.layout_extra_files = []
        self.metadata_dir = None
        self.pkginfo = None
        self.source_dir = Path.cwd()
        self.config_file = None
        self.state_file = None
        self.targets = Path(__file__).absolute().parent / "targets"
        self.wheel_tag = None
        self.abi_tag = None
        self.ext_suffix = None
        self.platform = None
        self.build_number = None
        self.sdist_name = None
        self.wheel_name = None
        self.distinfo_name = None
        self.python_cflags = None
        self.python_ldflags = None
        self.python_includes = None
        self.python_libs = None

    def finalize_metadata(self, getenv=os.getenv, sdist=False, in_place=False):
        if self._finalized:
            return
        self._finalized = True

        self.output_dir = self.source_dir / (self.output_dir or "dist")
        self.build_dir = self.source_dir / (self.build_dir or "build/bin")
        if self._perform_layout is None:
            self._perform_layout = bool(self.layout_dir)
        self.layout_dir = self.source_dir / (self.layout_dir or (self.build_dir / "layout"))
        self.temp_dir = self.source_dir / (self.temp_dir or "build/temp")
        self.pkginfo = self.source_dir / (self.pkginfo or "PKG-INFO")
        self.metadata_dir = self.temp_dir / (self.metadata_dir or "metadata")

        self._set_best("config_file", None, "PYMSBUILD_CONFIG", "_msbuild.py", getenv)
        self._set_best("state_file", None, "PYMSBUILD_STATE_FILE", (self.layout_dir / "__state.txt"), getenv)
        if self.state_file:
            self.state_file = Path(self.state_file)

        type(self).current = self

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
                try:
                    self.config.METADATA.update(self.metadata)
                except AttributeError:
                    self.config.METADATA = self.metadata
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
        if self.metadata is None:
            raise RuntimeError("failed to locate METADATA")

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

        self._set_best("ext_suffix", "ExtSuffix", "PYMSBUILD_EXT_SUFFIX", None, getenv)
        self._set_best("abi_tag", "AbiTag", "PYMSBUILD_ABI_TAG", None, getenv)
        self._set_best("wheel_tag", "WheelTag", "PYMSBUILD_WHEEL_TAG", None, getenv)
        self._set_best("platform", None, "PYMSBUILD_PLATFORM", None, getenv)
        self._set_best("configuration", None, "PYMSBUILD_CONFIGURATION", "Release", getenv)

        if in_place:
            default_target = "RelayoutInPlace" if self.force else "LayoutInPlace"
        elif sdist:
            default_target = "RelayoutSdist" if self.force else "LayoutSdist"
        else:
            default_target = "Relayout" if self.force else "Layout"
        self._set_best("target", None, "PYMSBUILD_TARGET", default_target, getenv)

        tags = _tags.choose_best_tags(
            ext_suffix = self.ext_suffix,
            abi_tag = self.abi_tag,
            wheel_tag = self.wheel_tag,
            platform_tag = self.platform,
        )
        self.ext_suffix = tags.ext_suffix
        self.abi_tag = tags.abi_tag
        self.wheel_tag = tags.wheel_tag
        self.platform = tags.platform_tag

        name, version = self.metadata["Name"], self.metadata["Version"]
        name = re.sub(r"[^\w\d.]+", "_", name, flags=re.UNICODE)
        version = re.sub(r"[^\w\d.]+", "_", version, flags=re.UNICODE)
        self._set_best("sdist_name", None, "PYMSBUILD_SDIST_NAME", "{}-{}.tar.gz".format(name, version), getenv)
        self._set_best("wheel_name", None, "PYMSBUILD_WHEEL_NAME", "{}-{}-{}.whl".format(name, version, self.wheel_tag), getenv)
        self._set_best("distinfo_name", None, "PYMSBUILD_DISTINFO_NAME", "{}-{}.dist-info".format(name, version), getenv)

        self._set_best("python_config", None, "PYTHON_CONFIG", None, getenv)
        self._set_best("python_includes", None, "PYTHON_INCLUDES", getenv("PYMSBUILD_PYTHON_INCLUDES"), getenv)
        self._set_best("python_libs", None, "PYTHON_LIBS", getenv("PYMSBUILD_PYTHON_LIBS"), getenv)

        if not self.python_includes:
            self.python_includes = sysconfig.get_config_var("INCLUDEPY")
        if not self.python_libs:
            if _WINDOWS:
                self.python_libs = PurePath(sysconfig.get_config_var("installed_base")) / "libs"
            else:
                self.python_libs = sysconfig.get_config_var("LIBPL")

        type(self).current = None

    def finalize(self, getenv=os.getenv, sdist=False, in_place=False):
        self.finalize_metadata(getenv, sdist, in_place)

        if self.package is None:
            type(self).current = self
            if hasattr(self.config, "init_PACKAGE"):
                self.log("Dynamically initialising PACKAGE")
                if sdist:
                    pack = self.config.init_PACKAGE(None)
                else:
                    pack = self.config.init_PACKAGE(str(self.wheel_tag))
                if pack:
                    self.config.PACKAGE = self.package
            self.package = self.config.PACKAGE
            type(self).current = None

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

        if not self._finalized:
            raise RuntimeError("BuildState must be finalized before generating the project")

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        if self.metadata is not None:
            self.pkginfo = self.temp_dir / "PKG-INFO"
            self.log("Generating", self.pkginfo)
            _generate.generate_distinfo(self.metadata, self.temp_dir, self.source_dir)

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
        self.log("Compiling", project, "with", *self.msbuild_exe, "({})".format(self.target))
        if not project.is_file():
            raise FileNotFoundError(project)
        properties.setdefault("Configuration", self.configuration)
        if not properties.get("Platform"):
            try:
                properties["Platform"] = _tags.remap_platform_to_msbuild(self.platform)
            except LookupError:
                self.write("WARNING:", self.platform, "is not a known platform. Projects may not compile")
                properties["Platform"] = self.platform
        properties.setdefault("HostPython", sys.executable)
        if sys.base_prefix != sys.prefix:
            base_host = getattr(sys, "_base_executable", None)
            if not base_host or base_host == sys.executable:
                base_host = Path(sys.base_prefix) / Path(sys.executable).relative_to(sys.prefix)
            properties.setdefault("BaseHostPython", base_host)
        else:
            properties.setdefault("BaseHostPython", sys.executable)
        properties.setdefault("PyMsbuildTargets", self.targets)
        properties.setdefault("_ProjectBuildTarget", self.target)
        properties.setdefault("SourceRootDir", self.source_dir)
        properties.setdefault("OutDir", self.build_dir)
        properties.setdefault("IntDir", self.temp_dir)
        properties.setdefault("LayoutDir", self.layout_dir)
        properties.setdefault("DistinfoDir", (self.metadata_dir / self.distinfo_name))
        sdist_dir = self.layout_dir / self.sdist_name
        if sdist_dir.match("*.tar.gz"):
            sdist_dir = sdist_dir.with_suffix("").with_suffix("")
        elif sdist_dir.match("*.zip"):
            sdist_dir = sdist_dir.with_suffix("")
        properties.setdefault("SdistDir", sdist_dir)
        properties.setdefault("DefaultExtSuffix", self.ext_suffix)
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
                if k in {"IntDir", "OutDir", "SourceDir", "LayoutDir"}:
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
        self.finalize(in_place=True)
        self.generate()
        self.build()

    def clean(self):
        self.finalize()
        p = self.config.PACKAGE
        self.project = self.temp_dir / (p.name + ".proj")
        if self.project.is_file():
            self.target = "Clean"
            self.build()

    def get_requires_for_build_sdist(self):
        self.finalize_metadata(sdist=True)
        reqs = self.metadata.get("BuildSdistRequires", [])
        if not isinstance(reqs, (list, tuple)):
            return [reqs]
        return reqs

    def layout_sdist(self, statefile=True):
        self.finalize(sdist=True)
        self.generate()

        if self.layout_dir.is_dir():
            self.log("Removing existing layout directory", self.layout_dir)
            shutil.rmtree(self.layout_dir)

        self.build()

        if not self.layout_dir.is_dir():
            raise RuntimeError(f"Build failed to create {self.layout_dir}")

        if statefile:
            self._write_state("pack_sdist")
            self.write("Wrote layout to", self.layout_dir)

    def build_sdist(self):
        self.finalize(sdist=True)
        if self._perform_layout:
            self.layout_sdist(statefile=True)
        else:
            self.layout_sdist(statefile=False)
            return self.pack_sdist()

    def pack_sdist(self, files=None):
        self.finalize(sdist=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        sdist = self.output_dir / self.sdist_name

        if self.sdist_name.casefold().endswith(".tar.gz".casefold()):
            tar_name = self.sdist_name[:-3]
        else:
            tar_name = self.sdist_name + ".tar"

        rel_files = _relative_to_layout(files, self.layout_dir)
        import gzip, tarfile
        with gzip.open(sdist, "w") as f_gz:
            with tarfile.TarFile.open(tar_name, "w", fileobj=f_gz, format=tarfile.PAX_FORMAT) as f:
                self.log("Packing files into", sdist)
                for n, rn in rel_files:
                    if n.match(str(self.state_file)):
                        continue
                    self.log("-", rn)
                    f.add(n, arcname=rn)
                self.log()
        self.write("Wrote sdist to", sdist)
        return sdist.name

    def get_requires_for_build_wheel(self):
        self.finalize_metadata()
        reqs = self.metadata.get("BuildWheelRequires", [])
        if not isinstance(reqs, (list, tuple)):
            return [reqs]
        return reqs

    def layout_wheel(self, statefile=True):
        self.finalize()
        self.generate()

        if self.layout_dir.is_dir():
            self.log("Removing existing layout directory", self.layout_dir)
            shutil.rmtree(self.layout_dir)

        self.build()

        if not self.layout_dir.is_dir():
            raise RuntimeError(f"Build failed to create {self.layout_dir}")

        if not self.metadata_dir.is_dir():
            self.prepare_wheel_distinfo()

        # Copy metadata_dir into layout_dir
        if self.metadata_dir != self.layout_dir:
            metadata = (self.metadata_dir / self.distinfo_name).glob("*")
            for n, rn in _relative_to_layout(metadata, self.metadata_dir):
                n2 = self.layout_dir / rn
                n2.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(n, n2)

        if statefile:
            self._write_state("pack_wheel")
            self.write("Wrote layout to", self.layout_dir)

    def build_wheel(self, metadata_dir=None):
        self.finalize()
        if metadata_dir:
            self.metadata_dir = Path(metadata_dir)
            if not self.metadata_dir.is_dir():
                self.prepare_wheel_distinfo()
        else:
            self.prepare_wheel_distinfo()
        if self._perform_layout:
            self.layout_wheel(statefile=True)
        else:
            self.layout_wheel(statefile=False)
            return self.pack_wheel()

    def pack_wheel(self, files=None):
        self.finalize()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        wheel = self.output_dir / self.wheel_name
        record = []
        record_files = []
        rel_files = _relative_to_layout(files, self.layout_dir)

        import zipfile
        with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as f:
            self.log("Packing files into", wheel)
            for n, rn in rel_files:
                if n.match(str(self.state_file)):
                    continue
                self.log("-", rn)
                record.append(_add_and_record(f, n, rn))
            for n in self.metadata_dir.glob(self.distinfo_name):
                if n.is_dir():
                    record_files.append(rf"{n.name}/RECORD")
                    record.append(rf"{n.name}/RECORD,,")
            record_file = "\n".join(record).encode("utf-8")
            for n in record_files:
                self.log("-", n)
                f.writestr(n, record_file)
            self.log()
        self.write("Wrote wheel to", wheel)
        return wheel.name

    def prepare_wheel_distinfo(self):
        self.finalize()
        self.generate()
        outdir = self.metadata_dir / self.distinfo_name
        outdir.mkdir(parents=True, exist_ok=True)
        from pymsbuild import __version__
        with open(outdir / "WHEEL", "w", encoding="utf-8") as f:
            print("Wheel-Version: 1.0", file=f)
            print("Generator: pymsbuild", __version__, file=f)
            if self.wheel_tag:
                print("Root-Is-Purelib:", str(self.wheel_tag).endswith("-none-any"), file=f)
                print("Tag:", self.wheel_tag, file=f)
            else:
                print("Root-Is-Purelib: True", file=f)
            if self.build_number:
                print("Build:", self.build_number, file=f)
        shutil.copy(self.pkginfo, outdir / "METADATA")
        return outdir.name

    def _write_state(self, cmd):
        with self.state_file.open("w", encoding="utf-8") as f:
            print("pack-command=", cmd, sep="", file=f)
            for k in dir(self):
                if not k.startswith("_") and not hasattr(type(self), k) and k not in {"layout_dir"}:
                    v = getattr(self, k)
                    if isinstance(v, (str, PurePath)):
                        print(k, "=", getattr(self, k), sep="", file=f)
            print("# BEGIN FILES", file=f)
            for n, rn in _relative_to_layout(None, self.layout_dir):
                print(rn, file=f)

    def pack(self):
        self.finalize()
        if not self.state_file or not self.state_file.is_file():
            raise RuntimeError("'--layout-dir' argument is required when invoking the 'pack' command")
        cmd = None
        with self.state_file.open("r", encoding="utf-8-sig") as f:
            for i in f:
                k, sep, v = i.strip().partition("=")
                if not sep:
                    break
                if k == "pack-command":
                    cmd = v
                elif not k.startswith("_") and hasattr(self, k) and not hasattr(type(self), k):
                    setattr(self, k, v)
                else:
                    self.log("Property", k, "from layout directory is ignored")
            for k in ["layout_dir", "output_dir", "build_dir", "temp_dir", "metadata_dir"]:
                v = getattr(self, k, None)
                if v:
                    setattr(self, k, Path(v))
            files = [self.layout_dir / i.strip() for i in f if i.strip()]
        extra = list(self.layout_extra_files or ())
        seen = set()
        while extra:
            i = (extra.pop(0) or "").strip()
            if i in seen:
                continue
            seen.add(i)
            if i.startswith("@"):
                with Path(i[1:]).open("r", encoding="utf-8-sig") as f:
                    extra.extend(f)
            elif i:
                files.append(self.layout_dir / i)
        if not cmd or cmd not in {'pack_sdist', 'pack_wheel'}:
            self.write("Layout appears to be corrupted. Please rerun the first stage again.")
            return
        return getattr(self, cmd)(files)

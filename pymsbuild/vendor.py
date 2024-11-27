import os
import re
import sys

from pathlib import PurePath, Path
from pymsbuild import get_current_build_state
from pymsbuild._types import *
from pymsbuild.dllpack import DllPackage, PydRedirect

__all__ = ["VendoredPackage", "VendoredDllPackage"]

def _norm(name):
    return re.sub(r"[^a-z0-9]", "_", name.lower())


class _VendoredMixin:
    __ALL = "$ALL_VENDORED"
    __FIND_ALL = "**/" + __ALL
    __site_cache = {}

    @classmethod
    def _name_from_spec(cls, spec):
        m = re.match(r"([A-Za-z0-9\-_.]+)\s*(.*)$", spec)
        if not m:
            raise ValueError(f"Unsupported package spec: {spec}")
        return _norm(m.groups()[0])

    @classmethod
    def collect_all_requirements(cls, build_wheel_requires, package):
        all_seen = set()
        for s in build_wheel_requires:
            all_seen.add(cls._name_from_spec(s))
        for m in package.findall(cls.__FIND_ALL):
            if cls._name_from_spec(m.spec) not in all_seen:
                build_wheel_requires.append(m.spec)
                all_seen.add(cls._name_from_spec(m.spec))

    @classmethod
    def collect_all(cls, package, tag):
        for m in package.findall(cls.__FIND_ALL):
            m.collect(tag)

    def _match(self, key):
        if key == self.__ALL:
            return True
        return PurePath(self.name).match(key)

    def collect(self, tag):
        found = 0
        site = self.__site_cache
        if not site:
            site.update({
                _norm(di.name.partition("-")[0]): di
                for p in sys.path
                for di in Path(p).glob("*.dist-info")
                if di.is_dir()
            })
        try:
            p = site[self._name_from_spec(self.spec)]
        except KeyError:
            raise LookupError(f"Package {self.spec} is not installed") from None
        source = p.parent
        with open(p / "RECORD", "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                filename, filehash, filesize = line.rsplit(",", 2)
                if filename.startswith(".."):
                    continue
                if self._add_vendor_member(source / filename, filename, filehash, filesize):
                    found += 1
        if get_current_build_state().verbose and not get_current_build_state().quiet:
            print(f"Vendoring {found} file{'s' if found != 1 else ''} for {self.name}")


class VendoredPackage(Package, _VendoredMixin):
    def __init__(self, spec, name=None, **options):
        name = name or self._name_from_spec(spec)
        options.setdefault("BuildWheelRequires", spec)
        super().__init__(name, **options)
        self.spec = spec

    def _add_vendor_member(self, source, name, filehash, filesize):
        if not self.options.get("as_search_path"):
            package, _, name = name.partition("/")
            if package != self.name:
                if package == f"{self.name}.py" and not name:
                    # Convert single-file packages to modules
                    name = "__init__.py"
                    package = None
                else:
                    return

        suffix = source.suffix.lower()
        if suffix == ".pyc":
            return
        kind = File
        if suffix == ".py":
            kind = PyFile
        self.members.append(kind(source, name, IncludeInSdist=False))
        return True


class VendoredDllPackage(DllPackage, _VendoredMixin):
    def __init__(self, spec, name=None, import_names=[], **options):
        name = name or self._name_from_spec(spec)
        options.setdefault("BuildWheelRequires", spec)
        options.setdefault("RootNamespace", name)
        super().__init__(name, **options)
        self.spec = spec
        if self.options.get("as_search_path"):
            raise ValueError("Cannot set 'as_search_path' on VendoredDllPackage")

    def _add_vendor_member(self, source, name, filehash, filesize):
        package, _, name = name.partition("/")
        if package != self.name:
            if package == f"{self.name}.py" and not name:
                # Convert single-file packages to modules
                name = "__init__.py"
                package = None
            else:
                return

        suffix = source.suffix.lower()
        if suffix == ".pyc":
            return
        kind = File
        if suffix in (".pyd", ".so", ".dylib"):
            kind = PydRedirect
        elif suffix == ".py":
            kind = PyFile
        self.members.append(kind(source, name, IncludeInSdist=False))
        return True

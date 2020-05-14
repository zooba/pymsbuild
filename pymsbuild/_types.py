from pathlib import Path, PurePath

__all__ = [
    "Metadata",
    "Package",
    "Project",
    "PydFile",
    "PyFile",
    "CSourceFile",
    "IncludeFile",
    "File",
]

def _extmap(*exts):
    return frozenset(map(str.casefold, exts))


class _Project:
    _NATIVE_BUILD = False
    options = {}

    def __init__(self, target_name, *members, root=None, **kwargs):
        self.target_name = target_name
        self.root = Path(root or ".")
        self.options = {**self.options, **kwargs}
        self._project_file = None
        self._explicit_project = False
        self._dependencies = []
        self._members = members

    def _get_sources(self, root, globber):
        root = PurePath(root) / self.root
        for m in self._members:
            if hasattr(m, "_get_sources"):
                for i, src, dst in m._get_sources(root, lambda s: globber(root / s)):
                    if dst:
                        yield i, src, self.target_name + "\\" + dst
                    else:
                        yield i, src, dst
            else:
                raise ValueError("Unsupported type '{}' in '{}'".format(
                    type(m).__name__, type(self).__name__
                ))


class Package(_Project):
    def build(self, distinfo):
        import pymsbuild
        for m in self._members:
            if not isinstance(m, Package) and isinstance(m, _Project):
                m.build(distinfo)
        pymsbuild._build((self, distinfo.data))


class PydFile(_Project):
    _NATIVE_BUILD = True
    options = {"TargetExt": ".pyd"}

    def build(self, distinfo):
        import pymsbuild
        for m in self._members:
            if not isinstance(m, Package) and isinstance(m, _Project):
                m.build(distinfo)
        pymsbuild._build((self, distinfo.data))


class Metadata:
    def __init__(self, **kwargs):
        self.data = kwargs


class File:
    _ITEMNAME = "Content"
    _SUBCLASSES = []

    def __init_subclass__(cls):
        File._SUBCLASSES.append(cls)

    def __init__(self, source, name=None, is_pattern=False):
        self.source = PurePath(source)
        self.name = name or self.source.name
        self.is_pattern = is_pattern

    @classmethod
    def collect(cls, pattern):
        return cls(Path(pattern), is_pattern=True)

    def _get_sources(self, root, globber):
        if not self.is_pattern:
            return [(self._ITEMNAME, root / self.source, self.name)]
        return [(self._ITEMNAME, f, f.name) for f in globber(self.source)]


class PyFile(File):
    _EXTENSIONS = _extmap(".py")


class Project(File):
    _EXTENSIONS = _extmap(".proj", ".vcxproj")


class CSourceFile(File):
    _ITEMNAME = "ClCompile"
    _EXTENSIONS = _extmap(".c", ".cpp", ".cxx")


class IncludeFile(File):
    _ITEMNAME = "ClInclude"
    _EXTENSIONS = _extmap(".h", ".hpp", ".hxx")


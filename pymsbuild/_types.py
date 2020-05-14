from pathlib import Path, PurePath

__all__ = [
    "Package",
    "Project",
    "PydFile",
    "PyFile",
    "SourceFile",
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
        self._dependencies = []
        self._members = members
        import pymsbuild
        pymsbuild._PROJECTS.get().append(self)

    def _get_sources(self, root, globber):
        root = PurePath(root) / self.root
        dest = PurePath(self.target_name)
        for m in self._members:
            if isinstance(m, _Project):
                yield "Project", root / (m.target_name + ".proj"), dest
            elif hasattr(m, "_get_sources"):
                for i, src, dst in m._get_sources(root, lambda s: globber(root / s)):
                    if dst:
                        yield i, src, dest / dst
                    else:
                        yield i, src, dst
            else:
                raise ValueError("Unsupported type '{}' in '{}'".format(
                    type(m).__name__, type(self).__name__
                ))

    def build(self, **distinfo):
        import pymsbuild
        pymsbuild._DISTINFO.get().update(distinfo)
        pymsbuild._BUILD_PROJECT.set(self)


class Package(_Project):
    pass


class PydFile(_Project):
    _NATIVE_BUILD = True
    options = {"TargetExt": ".pyd"}


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
            return [(self._ITEMNAME, root / self.source, PurePath(self.name))]
        return [(self._ITEMNAME, f, PurePath(f.name)) for f in globber(root / self.source)]


class PyFile(File):
    _EXTENSIONS = _extmap(".py")


class Project(File):
    _ITEMNAME = "Project"
    _EXTENSIONS = _extmap(".proj", ".vcxproj")


class SourceFile(File):
    _ITEMNAME = "Content"
    options = {"IncludeInWheel": False}


class CSourceFile(File):
    _ITEMNAME = "ClCompile"
    _EXTENSIONS = _extmap(".c", ".cpp", ".cxx")


class IncludeFile(File):
    _ITEMNAME = "ClInclude"
    _EXTENSIONS = _extmap(".h", ".hpp", ".hxx")


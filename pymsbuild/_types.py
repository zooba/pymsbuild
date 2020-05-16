from os import name
from pathlib import WindowsPath as Path, PureWindowsPath as PurePath

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
    _ACTIONS = ()
    options = {}

    def __init__(self, name, *members, project_file=None, **kwargs):
        self.name = name
        self.options = {**self.options, **kwargs}
        self.project_file = project_file
        self._members = members


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

    def __init__(self, source, name=None):
        self.source = PurePath(source)
        self.name = name or self.source.name
        self._members = []


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

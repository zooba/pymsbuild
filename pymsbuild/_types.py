from os import name
from pathlib import WindowsPath as Path, PureWindowsPath as PurePath

__all__ = [
    "Package",
    "Project",
    "PydFile",
    "LiteralXML",
    "ConditionalValue",
    "Property",
    "ItemDefinition",
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

    def __init__(self, name, *members, project_file=None, source="", **kwargs):
        self.name = name
        self.source = source
        self.options = {**self.options, **kwargs}
        self.project_file = project_file
        self.members = list(members)


class Package(_Project):
    pass


class PydFile(_Project):
    _NATIVE_BUILD = True
    options = {"TargetExt": ".pyd"}


class LiteralXML:
    members = ()

    def __init__(self, xml_string):
        self.name = "##xml"
        self.xml = xml_string


class ConditionalValue:
    """A wrapper for any metadata or property value to add a condition"""
    def __init__(self, value, *, condition=None, if_empty=None, prepend=False, append=False):
        self.value = value
        self.condition = condition
        self.if_empty = if_empty
        self.prepend = prepend
        self.append = append

    def __repr__(self):
        return repr(self.value)

    def __str__(self):
        return str(self.value)


class Property:
    members = ()

    def __init__(self, name, value):
        self.name = name
        self.value = value


class ItemDefinition:
    members = ()

    def __init__(self, kind, **metadata):
        self.name = "ItemDefinition/" + kind
        self.kind = kind
        self.options = metadata


class File:
    _ITEMNAME = "Content"
    _SUBCLASSES = []
    options = {}

    def __init_subclass__(cls):
        File._SUBCLASSES.append(cls)

    def __init__(self, source, name=None, **metadata):
        self.source = PurePath(source)
        self.name = name or self.source.name
        self.members = []
        self.options = {**self.options, **metadata}


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


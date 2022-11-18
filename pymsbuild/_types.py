from importlib.machinery import EXTENSION_SUFFIXES as _EXTENSION_SUFFIXES
from pathlib import Path, PurePath

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
    "RemoveFile",
]


class _Project:
    r"""Base class of compilable projects. Do not use directly."""
    options = {}

    def __init__(self, name, *members, project_file=None, source="", **options):
        self.name = name
        self.source = source
        self.options = {**self.options, **options}
        self.project_file = project_file
        self.members = list(members)

    def __iter__(self):
        for m in self.members:
            yield m
            try:
                it = iter(m)
            except TypeError:
                pass
            else:
                yield from it


class Package(_Project):
    r"""Represents a Python package.

Each Package represents a directory in the final distribution. Its
members may be other packages, files, or configuration settings.

Packages and files that are members of a Package will be installed
to the package directory. Note that only explicitly listed contents
will be included.

Specify `project_file` to override all generation with a fixed
MSBuild project file. This also overrides additional options and
sdist generation.

Specify `source` to find sources in a subdirectory without impacting
the install structure.

Other options will be added to the project as properties.
"""


class PydFile(_Project):
    r"""Represents a .pyd module.

Each PydFile represents a single .pyd file in the final distribution.
It must be included in a Package, and the built module will be
included in that package's directory.

Its members should be source files or projects. Directly referenced
files will be included in sdists, but transitive references will not.

Specify `project_file` to override all generation with a fixed
MSBuild project file. This also overrides additional options and
sdist generation.

Specify `source` to find sources in a subdirectory.

Other options will be added to the project as properties.
"""
    options = {"TargetExt": None}


class LiteralXML:
    r"""Literal string to insert into generated project file.

This must be valid XML and may use any MSBuild syntax. It will be
inserted under the top-level <Project> element.
"""
    members = ()

    def __init__(self, xml_string):
        self.name = "##xml"
        self.xml = xml_string


class ConditionalValue:
    r"""Add a condition to any property value.

This may be applied to any value that will be written into a project
file.

Specify `condition` to directly control the test, or `if_empty` to
check for an existing value.

Specify either `prepend` or `append` (or both, if you have a reason)
to concatenate the existing property value. Remember to include the
appropriate separator character in your value.
"""
    has_condition = True

    def __init__(self, value, *, condition=None, if_empty=False, prepend=False, append=False):
        self.value = value
        # Ensure condition has a True value so we can test for it later
        self.condition = condition
        self.if_empty = if_empty
        self.prepend = prepend
        self.append = append

    def __repr__(self):
        return "ConditionalValue(" + ", ".join(s for s in (
            "condition={}".format(self.condition) if self.condition else None,
            "if_empty=True" if self.if_empty else None,
            "prepend=True" if self.prepend else None,
            "append=True" if self.append else None,
        ) if s) + ")"

    def __str__(self):
        return str(self.value)


def Prepend(value):
    r"""Add a value that will prepend any existing value.

This is a helper function for ConditionalValue that sets `prepend` to True.
Remember to include the appropriate separator character in your value.
"""
    return ConditionalValue(value, prepend=True)


class Property:
    r"""Add a property to a project.

When generated into an MSBuild project, this property will be defined
at the point in member order where it is specified.

Use `ConditionalValue` to add conditions to the property.
"""
    members = ()

    def __init__(self, name, value):
        self.name = name
        self.value = value


class ItemDefinition:
    r"""Add an item definition to a project.

When generated into an MSBuild project, the item definition group will
be defined at the point in member order where it is specified.

Provide a list or tuple as the metadata value to include multiple
specifications.

Use `ConditionalValue` to add conditions to each metadata item.
"""
    members = ()

    def __init__(self, kind, **metadata):
        self.name = "ItemDefinition({})".format(kind)
        self.kind = kind
        self.options = metadata


class File:
    r"""Add a generic file to a package or project.

When added to `Package`, the file will be copied into the resulting
package directory.

When added to another project, behaviour will depend on how that
project treats "Content" elements.
"""
    _ITEMNAME = "Content"
    options = {}
    has_condition = False
    condition = None

    def __init__(self, source, name=None, **metadata):
        self.source = PurePath(source)
        self.name = name or self.source.name
        self.members = []
        self.options = {**self.options, **metadata}

    def excluding(self, pattern):
        self.has_condition = True
        self.exclude = pattern
        return self

    def if_(self, condition):
        self.has_condition = True
        self.condition = condition
        return self


class PyFile(File):
    r"""Add a Python source file to a package.

Currently does nothing special. One day will generate .pyc files.
"""
    options = {"GeneratePyc": True}


class Project(File):
    r"""Add a reference to an external MSBuild project.

This project should either provide Build, BuildSdist and BuildInPlace
targets, or import "$(PyMsbuildTargets)\common.targets". Otherwise,
files referenced or generated by this project are not automatically
included in sdists or wheels, or the projcet may cause the build to
fail.
"""
    _ITEMNAME = "Project"


class SourceFile(File):
    r"""Add a generic file to use for building.

These files will be included in the sdist, but will not be copied
in-place or included in wheels.
"""
    _ITEMNAME = "None"


class CSourceFile(File):
    r"""Add a C/C++ source file.

These files will be included in the sdist, but will not be copied
in-place or included in wheels, except as built output.

Incremental rebuilds will be triggered when these files are modified,
and each file is expected to produce a linkable file.
"""
    _ITEMNAME = "ClCompile"


class LinkFile(File):
    r"""Add a linker input file.

These files will be included in the sdist, but will not be copied
in-place or included in wheels, except as built output.

Incremental rebuilds will be triggered when these files are modified,
and each file will be linked into the final output.
"""
    _ITEMNAME = "Link"

class IncludeFile(File):
    r"""Add a header file.

These files will be included in the sdist, but will not be copied
in-place or included in wheels, except as built output.

Incremental rebuilds will be triggered when these files are modified,
but they do not produce linkable outputs.
"""
    _ITEMNAME = "ClInclude"

class RemoveFile:
    r"""Removes a file that has already been added.

This must appear after the files that were added, and must specify the
same kind (either the class used to create it, or the string literal
matching the MSBuild item name).
"""
    _ITEMNAME = None
    name = None
    members = ()
    has_condition = True
    condition = None

    def __init__(self, kind, pattern):
        self._ITEMNAME = getattr(kind, "_ITEMNAME", None) or str(kind)
        self.exclude = pattern

    def if_(self, condition):
        self.condition = condition

    def __str__(self):
        return ""

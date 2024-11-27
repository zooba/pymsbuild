import sys
from . import PYMSBUILD_REQUIRES_SPEC
from importlib.machinery import EXTENSION_SUFFIXES as _EXTENSION_SUFFIXES
from pathlib import Path, PurePath

__all__ = [
    "Package",
    "Project",
    "CProject",
    "PydFile",
    "VersionInfo",
    "LiteralXML",
    "ConditionalValue",
    "ExactNameMatchMixin",
    "Prepend",
    "Property",
    "ItemDefinition",
    "ImportGroup",
    "PyFile",
    "SourceFile",
    "CSourceFile",
    "IncludeFile",
    "File",
    "Midl",
    "Manifest",
    "RemoveFile",
    "PyprojectTomlFile",
]


def _recursive_iter(it):
    for m in it:
        yield m
        try:
            it = iter(m)
        except TypeError:
            pass
        else:
            yield from it


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
        return _recursive_iter(self.members)

    @staticmethod
    def _match_item(o, key):
        if key == "*":
            return True
        try:
            match = o._match
        except AttributeError:
            pass
        else:
            return match(key)
        try:
            name = o.name
        except AttributeError:
            pass
        else:
            return PurePath(name).match(key)
        return False

    def find(self, member_path, default=...):
        """Returns the first member matching the path.

Paths are as for 'findall'. If no member is found, ValueError is raised
unless 'default' is specified, in which case it is returned.
"""
        r = next(self.findall(member_path), default)
        if r is ...:
            raise ValueError(f"Unable to find '{member_path}'")
        return r

    def findall(self, member_path):
        """Returns an iterable of members matching the path.

Paths are slash-separated hierarchies of names matched according to
each member's own rules. By default, most members match their 'name'
property following file system rules (including name wildcards).

All matching levels of the path are collected. So a path of 'A/B/C'
will match multiple 'A's and 'B's return all the members beneath them
that match the full path 'A/B/C'.

A segment of '*' will match all members. Recursive wildcard segments
'**' are supported, but unlikely to be efficient (they perform a full
search of the remaining segments at every node).
"""
        if not member_path:
            return
        if isinstance(member_path, str):
            member_path = member_path.replace("\\", "/").split("/")
        p = member_path[0]

        if p == "**":
            next_path = member_path[1:]
            yield from self.findall(next_path)
            for m in _recursive_iter(self.members):
                try:
                    findall = m.findall
                except AttributeError:
                    pass
                else:
                    yield from findall(next_path)
            return

        matches = (m for m in self.members if self._match_item(m, p))
        if len(member_path) == 1:
            yield from matches
        else:
            next_path = member_path[1:]
            for m in matches:
                try:
                    findall = m.findall
                except AttributeError:
                    pass
                else:
                    yield from findall(next_path)

    def insert(self, member_path, member, *, offset=0, range=False):
        """Finds a member by path and inserts one before it.

Raises LookupError if no matching member could be found.
'offset' is added to the found member's index before inserting. Set to
1 to insert after the element."""
        if not member_path:
            self.members.append(member)
            return
        if isinstance(member_path, str):
            member_path = member_path.replace("\\", "/").split("/")
        p = member_path[0]
        if len(member_path) == 1:
            for i, m in enumerate(self.members):
                if self._match_item(m, p):
                    if range:
                        self.members[i + offset:i + offset] = member
                    else:
                        self.members.insert(i + offset, member)
                    return
        else:
            next_path = member_path[1:]
            for m in self.members:
                if self._match_item(m, p):
                    try:
                        insert = m.insert
                    except AttributeError:
                        pass
                    else:
                        return insert(next_path, member, offset=offset, range=range)
        raise LookupError("unable to locate requested member")


class ExactNameMatchMixin:
    r"""Mix-in class to suppress wildcards in findall()"""
    def _match(self, key):
        return key.casefold() == self.name.casefold()


class ImportGroup(ExactNameMatchMixin):
    r"""Helper for declaring a group of custom imports.

This is mainly intended for extenders, as most projects should not need
custom MSBuild imports. However, there's nothing stopping you from
using it!

Subclass this type and override 'name' and 'imports', then add an
instance into your Package definition.

class MyImport(ImportGroup):
    name = "$MyImport" # dollar sign avoids conflicts with filenames
    imports = [
        "path/to/my.targets",
    ]
"""
    name = "ImportGroup"
    members = ()
    imports = ()

    def __init__(self, *imports):
        self.imports = [*self.imports, *imports]

    def write_member(self, f, g):
        from os import fsdecode
        from os.path import sep as SEP
        g.switch_to("ImportGroup")
        for n in self.imports:
            c = None
            if getattr(n, "has_condition", False):
                c = n.condition
                n = n.value
            try:
                n = fsdecode(n).replace("/", SEP)
            except TypeError:
                n = str(n)
            f.add_import(n, c)


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


class CProject(_Project):
    r"""Represents a native binary.

Use PydFile to create a native Python extension module, unless
you are avoiding automatic filename generation.

Each CProject represents a single compiled file in the final
distribution. It must be included in a Package, and the built
file will be included in that package's directory.

By default it will produce a dynamic library. Specify
'ConfigurationType' as 'Application' or 'StaticLibrary' to change.

Its members should be source files or projects. Directly referenced
files will be included in sdists, but transitive references will not.

Specify `project_file` to override all generation with a fixed
MSBuild project file. This also overrides additional options and
sdist generation.

Specify `source` to find sources in a subdirectory.

Other options will be added to the project as properties.
"""
    options = {
        "ConfigurationType": "DynamicLibrary",
        "DynamicLibcppLinkage": "false",
    }

    def __init__(self, name, *members, **options):
        super().__init__(name, *members, **options)
        self.members = [
            self.GlobalProperties(self),
            self.DefaultToolsetProps(),
            self.ConfigurationProperties(self),
            self.ToolsetProps(),
            self.TargetExtProperty(self),
            self.ToolsetPydProps(),
            *self.members,
            self.ToolsetTargets(),
        ]


    class DefaultToolsetProps(ImportGroup):
        name = "$CProject.DefaultCppProps"
        imports = [
            "$(PyMsbuildTargets)/common.props",
            "$(PyMsbuildTargets)/cpp-default-$(Platform).props",
        ]


    class ToolsetProps(ImportGroup):
        name = "$CProject.CppImports"
        imports = [
            "$(PyMsbuildTargets)/cpp-$(Platform).props",
        ]

    class ToolsetPydProps(ImportGroup):
        name = "$CProject.PydProps"
        imports = [
            "$(PyMsbuildTargets)/pyd.props",
        ]


    class ToolsetTargets(ImportGroup):
        name = "$CProject.CppTargets"
        imports = [
            "$(PyMsbuildTargets)/common.targets",
            "$(PyMsbuildTargets)/cpp-$(Platform).targets",
            "$(PyMsbuildTargets)/pyd.targets",
        ]


    class GlobalProperties(ExactNameMatchMixin):
        r"""Special handling for C++ properties.

We need to defer some options until after the default imports. These
will be added by ConfigurationProperties. We also need to defer reading
from project.options until we're actually writing, as the author may
modify its contents.
"""
        members = ()
        name = "$CProject.GlobalProperties"
        defer = {"ConfigurationType", "TargetExt"}

        def __init__(self, project):
            self.project = project

        def write_member(self, f, g):
            g.switch_to("PropertyGroup")
            for k, v in self.project.options.items():
                if k not in self.defer:
                    f.add_property(k, v)


    class ConfigurationProperties(ExactNameMatchMixin):
        members = ()
        name = "$CProject.ConfigurationProperties"

        def __init__(self, project):
            self.project = project

        def write_member(self, f, g):
            g.switch_to("PropertyGroup")
            f.add_property("ConfigurationType", self.project.options.get("ConfigurationType") or "DynamicLibrary")
            f.add_property("PlatformToolset", "$(DefaultPlatformToolset)")
            f.add_property("BasePlatformToolset", "$(DefaultPlatformToolset)")
            f.add_property("CharacterSet", "Unicode")


    class TargetExtProperty(ExactNameMatchMixin):
        members = ()
        name = "$CProject.TargetExtProperty"

        def __init__(self, project):
            self.project = project

        def write_member(self, f, g):
            try:
                target_ext = self.project.options["TargetExt"]
            except LookupError:
                pass
            else:
                g.switch_to("PropertyGroup")
                f.add_property("TargetExt", target_ext)

    # BACK-COMPAT: Expose under old name as well
    DefaultToolsetImports = DefaultToolsetProps
    ToolsetImports = ToolsetProps


class PydFile(CProject):
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
    options = {
        **CProject.options,
        "ConfigurationType": "ExtensionModule",
        "LinkCompiled": "true",
        "OutputType": "library",
    }


class VersionInfo:
    r"""Represents version info to compile into a .pyd module.

Recommended usage is to add a default instance into your project and
in 'init_METADATA' find it again and pass in the final metadata.

PACKAGE = Package(
    "package",
    PydFile("mod1", VersionInfo()),
    PydFile("mod2", VersionInfo()),
)

def init_METADATA():
    METADATA["Version"] = "1.0"
    for vi in PACKAGE.findall("*/VersionInfo"):
        vi.from_metadata(METADATA)

See https://learn.microsoft.com/en-us/windows/win32/menurc/versioninfo-resource
for the full list of metadata.
"""
    _ITEMNAME = "PydVersionInfo"
    name = "VersionInfo"
    members = ()

    options = {
        "FILEVERSION": "0,0,0,0",
        "PRODUCTVERSION": "0,0,0,0",
        "FILEFLAGSMASK": "VS_FFI_FILEFLAGSMASK",
        "FILEFLAGS": "0",
        "FILEOS": "VOS_NT",
        "FILETYPE": "VFT_DLL",
        "FILESUBTYPE": "0",
        "Comments": "",
        "CompanyName": "",
        "FileDescription": "",
        "FileVersion": "",
        "InternalName": "",
        "LegalCopyright": "",
        "LegalTrademarks": "",
        "OriginalFilename": "$(TargetName)$(TargetExt)",
        "PrivateBuild": "",
        "ProductName": "",
        "ProductVersion": "",
        "SpecialBuild": "",
        "LangId": "0x0409",
        "CharsetId": "1200",
    }

    def __init__(self, **options):
        self.options = {
            **self.options,
            **options,
        }

    @staticmethod
    def _read_version(version):
        vv = []
        for v in version.split(".", 5):
            try:
                int(v)
            except (OverflowError, ValueError):
                break
            else:
                vv.append(v)
        return ", ".join((*vv, "0", "0", "0", "0")[:4])

    def from_metadata(self, metadata):
        ver = metadata["Version"]
        self.update(False, **dict(
            FILEVERSION=self._read_version(ver),
            PRODUCTVERSION=self._read_version(ver),
            CompanyName=metadata.get("Author"),
            FileDescription=metadata.get("Summary"),
            FileVersion=ver,
            InternalName=metadata.get("Name"),
            ProductName=metadata.get("Name"),
            ProductVersion=ver,
        ))

    def update(self, overwrite=True, **values):
        for k, v in values.items():
            if overwrite or (v and not self.options.setdefault(k, v)):
                self.options[k] = v

    def _match(self, key):
        return key.casefold() == "versioninfo".casefold()

    def write_member(self, project, group):
        group.switch_to("ItemGroup")
        opts = {**self.options}
        langid = opts.get("LangId", "0x0409")
        try:
            langid = int(langid, 0)
        except ValueError:
            langid = 0x0409
        charsetid = opts.get("CharsetId", "1200")
        try:
            charsetid = int(charsetid, 0)
        except ValueError:
            charsetid = 1200
        encoding = "Unicode" if charsetid == 1200 else "ASCII"
        opts.update({
            "LangId": f"0x{langid:04X}",
            "CharsetId": str(charsetid),
            "LangCharset": f"{langid:04X}{charsetid:04X}",
            "Encoding": encoding,
        })
        for k in ["FileVersion", "ProductVersion", "FileFlagsMask", "FileFlags", "FileOS", "FileType", "FileSubType"]:
            v = opts.pop(k.upper(), None)
            if v:
                opts[f"_{k}"] = v
        
        for k in list(opts):
            if not opts.get(k):
                del opts[k]
        project.add_item(self._ITEMNAME, self.name, **opts)


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
    options = {
        "IncludeInSdist": True,
        "IncludeInLayout": True,
        "IncludeInWheel": True,
    }
    has_condition = False
    condition = None

    def __init__(self, source, name=None, **metadata):
        self.source = PurePath(source)
        self.name = name or self.source.name
        self.members = []
        overrides = {}
        if self.source.parts[0].startswith("$("):
            overrides["IncludeInSdist"] = False
        if self.name.startswith("$("):
            self.name = self.name.partition(")")[2]
        self.options = {**self.options, **overrides, **metadata}

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
    options = {
        "GeneratePyc": True,
        "IncludeInSdist": True,
        "IncludeInLayout": True,
        "IncludeInWheel": True,
    }


class Project(File):
    r"""Add a reference to an external MSBuild project.

This project should provide Build, GetPackageFiles and GetSdistFiles
targets, or import "$(PyMsbuildTargets)\common.{props,targets}".
Otherwise, files referenced or generated by this project are not
automatically included in sdists or wheels, or the project may cause
the build to fail.
"""
    _ITEMNAME = "Project"
    options = {
        "IntDir": "$(IntDir)%(Filename)",
        "TargetDir": "$(TargetName)",
        "SourceDir": "$(SourceDir)",
        "IncludeInSdist": True,
        "IncludeInLayout": False,
        "IncludeInWheel": False,
    }


class SourceFile(File):
    r"""Add a generic file to use for building.

These files will be included in the sdist, but will not be copied
in-place or included in wheels.
"""
    _ITEMNAME = "None"
    options = {
        "IncludeInSdist": True,
        "IncludeInLayout": False,
        "IncludeInWheel": False,
    }


class CSourceFile(SourceFile):
    r"""Add a C/C++ source file.

These files will be included in the sdist, but will not be copied
in-place or included in wheels, except as built output.

Incremental rebuilds will be triggered when these files are modified,
and each file is expected to produce a linkable file.
"""
    _ITEMNAME = "ClCompile"


class LinkFile(SourceFile):
    r"""Add a linker input file.

These files will be included in the sdist, but will not be copied
in-place or included in wheels, except as built output.

Incremental rebuilds will be triggered when these files are modified,
and each file will be linked into the final output.
"""
    _ITEMNAME = "Link"


class IncludeFile(SourceFile):
    r"""Add a header file.

These files will be included in the sdist, but will not be copied
in-place or included in wheels, except as built output.

Incremental rebuilds will be triggered when these files are modified,
but they do not produce linkable outputs.
"""
    _ITEMNAME = "ClInclude"


class RemoveFile(File):
    r"""Removes a file that has already been added.

Note that all matching files will be removed. You cannot add the file
again after this has been specified. The 'Kind' is accepted as either
a string or the type object, but is not used.
"""
    _ITEMNAME = "_ExcludeFile"
    options = {}

    def __init__(self, kind, source, name=None):
        super().__init__(
            source,
            name, 
            Kind=getattr(kind, "_ITEMNAME", None) or str(kind),
        )

class Midl(File):
    r"""Add an interface definition language source.

These files are compiled using the MIDL tool to generate headers that
are included by your own code.

See https://learn.microsoft.com/uwp/midl-3/ for more information.
"""
    _ITEMNAME = "Midl"
    options = {
        **File.options,
        "Subtype": "Code",
    }

class Manifest(File):
    r"""Add an application manifest file.

The manifest is embedded into a Windows executable file to provide
additional settings.

See https://learn.microsoft.com/windows/win32/sbscs/application-manifests
for more information.
"""
    _ITEMNAME = "Manifest"


class PyprojectTomlFile(ExactNameMatchMixin):
    r"""Add a generated pyproject.toml file.

The file is generated for the sdist based on the arguments passed to
the constructor, or by calling from_metadata(METADATA):

def init_METADATA():
    PACKAGE.find("pyproject.toml").from_metadata(METADATA)

If a source file is passed, tables other than 'project' are used in the
generated project. Otherwise, a default 'build-system' table is created.

To include a pyproject.toml without replacing any contents, specify it
as SourceFile('pyproject.toml').

The static PyprojectTomlFile.update_metadata(METADATA) function allows
loading supported fields from a pyproject.toml's 'project' table into
the METADATA. You will still need to call 'from_metadata()' to fill a
generated pyproject.toml, or include the original using a SourceFile.
"""
    name = "pyproject.toml"
    members = ()

    def __init__(self, source=None, content=None, **options):
        self.source = source
        self.options = options
        self._content = content

    @classmethod
    def _email_format(cls, a):
        try:
            return f"{a['name']} <{a['email']}>"
        except LookupError:
            return a.get('name') or str(a)

    @classmethod
    def update_metadata(cls, metadata, file="pyproject.toml", overwrite=False):
        """Uses pyproject.toml's project table to fill in METADATA.

Pass overwrite=True to replace existing fields.

Raises NotImplementedError if a supported toml library is not found.
"""
        try:
            from tomllib import loads
        except ImportError:
            try:
                from tomli import loads
            except ImportError:
                raise NotImplementedError("require 'tomli' to update metadata") from None

        file = Path(file).absolute()
        project = loads(file.read_text(encoding="utf-8"))['project']

        def c(from_key, to_key, xform=None, from_map=project):
            from_key = from_key.split(".")
            try:
                for bit in from_key[:-1]:
                    from_map = from_map[bit]
                v = from_map[from_key[-1]]
            except LookupError:
                return False
            if xform:
                v = xform(v)
            if overwrite:
                metadata[to_key] = v
            else:
                metadata.setdefault(to_key, v)
            return True

        c("name", "Name")
        c("version", "Version")
        c("description", "Summary")
        if not c("readme.text", "Description"):
            c("readme.file", "Description", File)
        c("readme.content-type", "Description-Content-Type")
        c("requires-python", "Requires-Python")
        if not c("license.text", "License"):
            c("license.file", "License", File)

        def str_or_list(fmt):
            def _f(v):
                if isinstance(v, str):
                    return v
                return ", ".join(map(fmt, v))
            return _f

        c("authors", "Author", str_or_list(cls._email_format))
        c("maintainers", "Maintainer", str_or_list(cls._email_format))
        c("keywords", "Keywords", str_or_list(str))
        c("classifiers", "Classifier")
        c("urls", "Project-url", lambda v: [f"{k}, {v[k]}" for k in v])
        c("dependencies", "Requires-Dist")
        c("dynamic", "Dynamic")

    def from_metadata(self, metadata):
        """Uses METADATA values to fill gaps in the generated pyproject.toml."""
        def c(from_key, to_key, xform=None, from_map=metadata, to_map=self.options, text_or_file=False):
            try:
                v = from_map[from_key]
            except LookupError:
                return False
            if text_or_file:
                try:
                    v = str(v.source)
                    to_key += ".file"
                except AttributeError:
                    to_key += ".text"
            if xform:
                v = xform(v)
            to_key = to_key.split(".")
            for bit in to_key[:-1]:
                to_map = to_map.setdefault(bit, {})
            to_map.setdefault(to_key[-1], v)
            return True
        c("Name", "name")
        c("Version", "version")
        c("Summary", "description")
        c("Description", "readme", text_or_file=True)
        c("Description-Content-Type", "readme.content-type")
        c("Requires-Python", "requires-python")
        c("License", "license", text_or_file=True)
        authors = {}
        c("Author", "name", to_map=authors)
        c("Author-email", "email", to_map=authors)
        if authors:
            self.options.setdefault("authors", [authors])
        maintainers = {}
        c("Maintainer", "name", to_map=maintainers)
        c("Maintainer-email", "email", to_map=maintainers)
        if maintainers:
            self.options.setdefault("maintainers", [maintainers])
        c("Keywords", "keywords", lambda v: [s.strip() for s in v.split(",")])
        c("Classifier", "classifiers")
        c("Project-url", "urls", lambda v: {i[0].strip(): i[2].strip() for u in v for i in [u.partition(",")]})
        c("Home-page", "urls.homepage")
        c("Download-URL", "urls.download")
        c("Requires-Dist", "dependencies")
        c("Dynamic", "dynamic")

    @classmethod
    def _toml_repr(cls, v):
        if isinstance(v, dict):
            return '{' + ', '.join(f'{cls._toml_repr(k)}={cls._toml_repr(v[k])}' for k in v) + '}'
        try:
            it = iter(v)
            f = next(it)
            if type(f) != type(v):
                return '[' + ', '.join(map(cls._toml_repr, [f, *it])) + ']'
        except (TypeError, StopIteration):
            pass
        if isinstance(v, str):
            if "'" in v or "\n" in v:
                return "'''" + v + "'''"
            return repr(v)
        return repr(v)

    @property
    def content(self):
        if self._content is not None:
            return self._content

        from io import StringIO
        f = StringIO()

        if self.source:
            with open(self.source) as f2:
                in_project = False
                for line in f2:
                    if line.strip() == '[project]':
                        in_project = True
                    elif line.strip().startswith('['):
                        in_project = False
                        print(line, end="", file=f)
                    elif not in_project:
                        print(line, end="", file=f)
            print(file=f)
        else:
            print('[build-system]', file=f)
            print('requires = ["{}"]'.format(PYMSBUILD_REQUIRES_SPEC), file=f)
            print('build-backend = "pymsbuild"', file=f)
            print(file=f)

        opts = self.options
        if opts:
            print('# Note that pymsbuild does not use this metadata.', file=f)
            print('# To update the final metadata, you need to update PKG-INFO.', file=f)
            print('[project]', file=f)
            for k in opts:
                try:
                    v = self._toml_repr(opts[k])
                except LookupError:
                    continue
                print('{}={}'.format(k, v), file=f)

        self._content = f.getvalue()
        try:
            from tomllib import loads
        except ImportError:
            try:
                from tomli import loads
            except ImportError:
                loads = lambda _: None
        try:
            # Sanity check the output if we can
            loads(self._content)
        except Exception:
            print("Failed to validate generated pyproject.toml:", file=sys.stderr)
            print(self._content, file=sys.stderr)
            raise
        return self._content

    def write_member(self, project, group):
        group.switch_to("PropertyGroup")
        project.add_property("_PyprojectTomlContent", "<![CDATA[" + self.content + "]]>")

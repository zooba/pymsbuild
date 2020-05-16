import contextlib
from importlib.resources import read_text
import uuid

_GENERATED_NAMESPACE = uuid.UUID('db509c23-800c-41d5-9d00-359fc120e87a')

PROLOGUE = r"""<?xml version="1.0" encoding="utf-8"?>
<Project DefaultTargets="Build" ToolsVersion="Current" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">"""

TARGETS = read_text(__name__, "targets.txt")
VCTARGETS = read_text(__name__, "vctargets.txt")


def _guid(target_name):
    return uuid.uuid3(_GENERATED_NAMESPACE, target_name)


class ProjectFileWriter:
    def __init__(self, filename, target_name, *, vc_platforms=None):
        self.filename = filename
        self.target_name = target_name
        self._file = None
        self._vc_platforms = vc_platforms
        self.indent = 2

    def __enter__(self):
        self._file = open(self.filename, "w", encoding="utf-8")
        print(PROLOGUE, file=self._file)
        if self._vc_platforms is True:
            self.add_vc_platforms()
        elif self._vc_platforms:
            self.add_vc_platforms(*self._vc_platforms)
        with self.group("PropertyGroup", Label="Globals"):
            self.add_property("Configuration", "Release", if_empty=True)
            self.add_property("Platform", "x64", if_empty=True)
            self.add_property("ProjectGuid", _guid(self.target_name))
            self.add_property("RootNamespace", self.target_name)
            self.add_property("TargetName", self.target_name)
        return self

    def __exit__(self, *exc_info):
        print("</Project>", file=self._file)
        self._file.flush()
        self._file.close()
        self._file = None

    def write(self, *text):
        print(" " * self.indent, *text, sep="", file=self._file)

    @contextlib.contextmanager
    def group(self, tag, **attributes):
        if attributes:
            self.write("<", tag, *(' {}="{}"'.format(*i) for i in attributes.items()), ">")
        else:
            self.write("<", tag, ">")
        self.indent += 2
        yield
        self.indent -= 2
        self.write("</", tag, ">")

    def add_property(self, name, value, condition=None, *, if_empty=False):
        if if_empty:
            condition = "$({}) == ''{}".format(name, " and {}".format(condition) if condition else "")
        if condition:
            self.write("<", name, ' Condition="', condition, '">', value, "</", name, ">")
        else:
            self.write("<", name, ">", value, "</", name, ">")

    def add_item(self, kind, name, **metadata):
        if metadata:
            with self.group(kind, Include=name):
                for k, v in metadata.items():
                    self.write("<", k, ">", v, "</", k, ">")
        else:
            self.write("<", kind, ' Include="', name, '" />')

    def add_item_property(self, kind, name, value, condition=None):
        if condition:
            self.write("<", name, 'Condition="', condition, '">', value, "</", name, ">")
        else:
            self.write("<", name, ">", value, "</", name, ">")

    def add_import(self, project):
        self.write('<Import Project="', project, '" />')

    def add_vc_platforms(self, platforms=None, configurations=None):
        if not platforms:
            platforms = ["Win32", "x64", "ARM", "ARM64"]
        if not configurations:
            configurations = ["Debug", "Release"]
        with self.group("ItemGroup", Label="ProjectConfigurations"):
            for c in configurations:
                for p in platforms:
                    with self.group("ProjectConfiguration", Include="{}|{}".format(c, p)):
                        self.add_property("Configuration", c)
                        self.add_property("Platform", p)

    def add_text(self, text):
        for line in text.splitlines():
            self.write(line)

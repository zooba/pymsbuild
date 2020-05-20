import contextlib
import uuid

from pathlib import Path

_GENERATED_NAMESPACE = uuid.UUID('db509c23-800c-41d5-9d00-359fc120e87a')

PROLOGUE = r"""<?xml version="1.0" encoding="utf-8"?>
<Project DefaultTargets="Build" ToolsVersion="Current" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">"""


TARGETS = Path(__file__).parent / "targets"


def _guid(target_name):
    return uuid.uuid3(_GENERATED_NAMESPACE, target_name)


class CV:
    def __init__(self, value, condition=None, if_empty=False):
        self.value = value
        self.condition = condition
        self.if_empty = if_empty


class ProjectFileWriter:
    def __init__(self, filename, target_name, *, vc_platforms=None):
        self.filename = filename
        self.target_name = target_name
        self._file = None
        self._vc_platforms = vc_platforms
        self.indent = 2
        self.current_group = None

    def __enter__(self):
        self._file = open(self.filename, "w", encoding="utf-8")
        print(PROLOGUE, file=self._file)
        if self._vc_platforms is True:
            self.add_vc_platforms()
        elif self._vc_platforms:
            self.add_vc_platforms(*self._vc_platforms)
        with self.group("PropertyGroup", Label="Globals"):
            self.add_property("Configuration", CV("Release", "$(Release) == ''"))
            self.add_property("Platform", CV("x64", "$(Platform) == ''"))
            self.add_property("ProjectGuid", _guid(self.target_name))
            self.add_property("RootNamespace", self.target_name)
            self.add_property("TargetName", self.target_name)
            self.add_property("_TargetsRoot", CV(TARGETS, if_empty=True))
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
        old_group, self.current_group = self.current_group, tag
        yield
        self.current_group = old_group
        self.indent -= 2
        self.write("</", tag, ">")

    def _write_value(self, name, value, symbol='$'):
        if isinstance(value, (tuple, list)):
            for v in value:
                self._write_value(name, v, symbol)
            return
        if hasattr(value, "condition"):
            if getattr(value, "if_empty", None):
                self.write("<", name, ' Condition="', symbol, "(", name, ") == ''\">", value.value, "</", name, ">")
            else:
                self.write("<", name, ' Condition="', value.condition, '">', value.value, "</", name, ">")
        else:
            self.write("<", name, ">", value, "</", name, ">")

    def add_property(self, name, value):
        self._write_value(name, value, "$")

    def add_item(self, kind, name, **metadata):
        if metadata:
            with self.group(kind, Include=name):
                for k, v in metadata.items():
                    self._write_value(k, v, "%")
        else:
            self.write("<", kind, ' Include="', name, '" />')

    def add_item_property(self, kind, name, value):
        self._write_value(name, value, "%")

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

import contextlib
import io
import uuid

from pathlib import Path

_GENERATED_NAMESPACE = uuid.UUID('db509c23-800c-41d5-9d00-359fc120e87a')

PROLOGUE = r"""<?xml version="1.0" encoding="utf-8"?>
<Project DefaultTargets="Build" ToolsVersion="Current" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">"""


TARGETS = Path(__file__).parent / "targets"


def _guid(target_name):
    return uuid.uuid3(_GENERATED_NAMESPACE, target_name)


class CV:
    has_condition = True

    def __init__(self, value, condition=None, if_empty=False):
        self.value = str(value)
        self.condition = condition
        self.if_empty = if_empty

    def __str__(self):
        return self.value


class ProjectFileWriter:
    def __init__(self, filename, target_name, *, vc_platforms=None, root_namespace=None):
        self.filename = filename
        self.target_name = target_name
        self.root_namespace = root_namespace or target_name
        self._file = None
        self._vc_platforms = vc_platforms
        self.indent = 2
        self.current_group = None

    def __enter__(self):
        Path(self.filename).parent.mkdir(parents=True, exist_ok=True)
        self._file = io.StringIO()
        print(PROLOGUE, file=self._file)
        if self._vc_platforms is True:
            self.add_vc_platforms()
        elif self._vc_platforms:
            self.add_vc_platforms(*self._vc_platforms)
        with self.group("PropertyGroup", Label="Globals"):
            self.add_property("Configuration", CV("Release", "$(Configuration) == ''"))
            self.add_property("Platform", CV("x64", "$(Platform) == ''"))
            self.add_property("ProjectGuid", _guid(self.target_name))
            self.add_property("RootNamespace", self.root_namespace)
            self.add_property("TargetName", self.target_name)
            self.add_property("PyMsbuildTargets", CV(TARGETS, if_empty=True))
        return self

    def __exit__(self, *exc_info):
        print("</Project>", file=self._file)
        try:
            with open(self.filename, "r", encoding="utf-8-sig") as f:
                old = f.read()
        except Exception:
            old = None
        if old != self._file.getvalue():
            with open(self.filename, "w", encoding="utf-8") as f:
                f.write(self._file.getvalue())
        self._file = None

    def write(self, *text):
        print(" " * self.indent, *text, sep="", file=self._file)

    @contextlib.contextmanager
    def group(self, tag, **attributes):
        if attributes:
            self.write("<", tag, *(' {}="{}"'.format(*i) for i in attributes.items() if all(i)), ">")
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
        c = None
        v = str(value)
        if getattr(value, "has_condition", None):
            c = value.condition
            if getattr(value, "if_empty", False):
                c = "{}({}) == ''".format(symbol, name)
            if getattr(value, "append", False):
                v = "{}({}){}".format(symbol, name, v)
            if getattr(value, "prepend", False):
                v = "{}{}({})".format(v, symbol, name)
        if c:
            self.write("<", name, ' Condition="', c, '">', v, "</", name, ">")
        else:
            self.write("<", name, ">", v, "</", name, ">")

    def add_property(self, name, value):
        self._write_value(name, value, "$")

    def add_item(self, kind, name, **metadata):
        c = None
        excl = None
        remove = None
        if getattr(name, "has_condition", False):
            c = name.condition
            excl = getattr(name, "exclude", None)
            remove = getattr(name, "remove", None)
            if getattr(name, "if_empty", False):
                c = "@({}) == ''".format(kind)
            if getattr(name, "append", False) or getattr(name, "prepend", False):
                raise ValueError("'append' and 'prepend' are not supported on '{}'".format(name))

        attrs = dict(Include=str(name), Condition=c, Exclude=excl, Remove=remove)
        attrs = {k: v for k, v in attrs.items() if v}
        if metadata:
            with self.group(kind, **attrs):
                for k, v in metadata.items():
                    if v is not None:
                        self._write_value(k, v, "%")
        else:
            self.write("<", kind, *[f' {k}="{v}"' for k, v in attrs.items()], " />")

    def add_item_property(self, kind, name, value):
        self._write_value(name, value, "%")

    def add_import(self, project, condition=None):
        if condition:
            self.write('<Import Project="', project, '" Condition="', condition, '"/>')
        else:
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

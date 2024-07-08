import os

from pymsbuild._types import *


class Entrypoint(PydFile):
    r"""Represents an executable that loads Python and calls your function.
"""
    class EntrypointProps:
        members = ()
        name = "$Entrypoint.EntrypointProps"
        def write_member(self, f, g):
            g.switch_to(None)
            f.add_import(f"$(PyMsbuildTargets){os.path.sep}entrypoint.props")

    class Imports(ImportGroup):
        name = "$Entrypoint.Imports"
        imports = [f"$(PyMsbuildTargets){os.path.sep}entrypoint.targets"]

    def __init__(self, name, module, function, *members, **kwargs):
        kwargs.setdefault("ConfigurationType", "Application")
        kwargs.setdefault("EntrypointModule", module)
        kwargs.setdefault("EntrypointFunction", function)
        kwargs.setdefault("TargetExt", ".exe")
        super().__init__(name, *members, **kwargs)
        self.insert(
            PydFile.GlobalProperties.name,
            self.EntrypointProps(),
            offset=1,
        )
        self.members.append(self.Imports())


class Icon(File):
    r"""Represents an icon resource.
"""
    _ITEMNAME = "EntrypointIcon"
    options = {
        **File.options,
        "IncludeInLayout": False,
        "IncludeInWheel": False,
    }


class SearchPath:
    r"""Represents a search path in an entrypoint executable.

Paths are relative to the location of the executable."""
    _ITEMNAME = "EntrypointPythonPath"
    members = ()
    options = {}

    def __init__(self, name, **options):
        self.name = name
        self.options = {
            **self.options,
            **options,
        }

    def write_member(self, project, group):
        group.switch_to("ItemGroup")
        project.add_item(self._ITEMNAME, self.name, **self.options)

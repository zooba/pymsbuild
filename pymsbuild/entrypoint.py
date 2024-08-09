import os

from pymsbuild._types import *

__all__ = ['Entrypoint', 'Icon', 'SearchPath', 'DefaultSearchPath']

class Entrypoint(CProject):
    r"""Represents an executable that loads Python and calls your function.
"""

    class EntrypointProps:
        members = ()
        name = "$Entrypoint.EntrypointProps"
        def write_member(self, f, g):
            g.switch_to(None)
            f.add_import(f"$(PyMsbuildTargets){os.path.sep}entrypoint.props")

    class EntrypointImports(ImportGroup):
        name = "$Entrypoint.Imports"
        imports = [f"$(PyMsbuildTargets){os.path.sep}entrypoint.targets"]

    def __init__(self, name, module, function, *members, **kwargs):
        kwargs.setdefault("ConfigurationType", "Application")
        kwargs.setdefault("EntrypointModule", module)
        kwargs.setdefault("EntrypointFunction", function)
        super().__init__(name, *members, **kwargs)
        self.insert(
            CProject.GlobalProperties.name,
            self.EntrypointProps(),
            offset=1,
        )
        self.members.append(self.EntrypointImports())


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


class DefaultSearchPath(SearchPath):
    r"""Represents a default Python search path.

This will vary depending on how Python is being included or referenced
from the built executable. For portability/relocatability, you are
advised to avoid this option. However, it's fine for when building to
run on the same machine.
"""
    _ITEMNAME = "DefaultEntrypointPythonPath"

    def __init__(self, name="$DefaultPythonPath", **options):
        super().__init__(name, **options)

from pymsbuild._types import *

class DllPackage(PydFile):
    r"""Represents a DLL-packed package.

This is the equivalent of a regular `Package`, but the output is a
compiled DLL that exposes submodules and resources using an import hook.

Add `Function` elements to link """
    options = {
        **PydFile.options,
    }

    def __init__(self, name, *members, project_file=None, **kwargs):
        super().__init__(
            name,
            *members,
            LiteralXML('<Import Project="$(PyMsbuildTargets)\\dllpack.targets" />'),
            project_file=project_file,
            **kwargs
        )


class CFunction:
    r"""Represents a function exposed in a DLL-packed package.

The named function must be provided in a `CSourceFile` element and
follow this prototype:

```
PyObject *function(PyObject *module, PyObject *args, PyObject *kwargs)
```

It will be available in the root of the package as the same name.
"""
    _ITEMNAME = "DllPackFunction"

    def __init__(self, name, **options):
        self.name = name
        self.options = dict(**options)

    def write_member(self, project, group):
        group.switch_to("ItemGroup")
        project.add_item(self._ITEMNAME, self.name, **self.options)

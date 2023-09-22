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
        self.members = []
        self.options = dict(**options)

    def write_member(self, project, group):
        group.switch_to("ItemGroup")
        project.add_item(self._ITEMNAME, self.name, **self.options)


class DllRedirect:
    r"""Represents a redirected extension module.

The name would normally be resolved within the packed DLL. However, for
.pyd files normally nested into a package, they need to be directed to
an adjacent file. The 'redirect_to' name will be loaded from the same
directory as the packed DLL using the default extension module loader.

The target module is not automatically included in the package.
"""
    _ITEMNAME = "DllPackRedirect"

    def __init__(self, name, redirect_to, **options):
        self.name = name
        self.members = []
        self.options = {
            "RedirectTo": redirect_to,
            **options
        }

    def write_member(self, project, group):
        group.switch_to("ItemGroup")
        project.add_item(self._ITEMNAME, self.name, **self.options)
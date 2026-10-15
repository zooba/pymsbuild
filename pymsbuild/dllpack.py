from pymsbuild._types import *

class DllPackage(PydFile):
    r"""Represents a DLL-packed package.

This is the equivalent of a regular `Package`, but the output is a
compiled DLL that exposes submodules and resources using an import hook.

Add `Function` elements to link """
    options = {
        **PydFile.options,
        "EncryptionKeyVariable": "",
    }

    class Imports(ImportGroup):
        name = "$DllPackage.Imports"
        imports = ["$(PyMsbuildTargets)/dllpack.targets"]

    def __init__(self, name, *members, project_file=None, **options):
        super().__init__(
            name,
            *members,
            self.Imports(),
            project_file=project_file,
            **options
        )

    def iter_wheel(self, prefix):
        name = self.options.get("TargetName") or self.name
        suffix = self.options.get("TargetExt", self._check_suffix)
        yield prefix / f"{name}{suffix}"
        yield from self._iter_redirects(self.members, prefix, prefix / self.name)

    @classmethod
    def _iter_redirects(cls, members, prefix, content_prefix):
        for member in members:
            if isinstance(member, CProject):
                yield from member.iter_wheel(prefix)
            elif isinstance(member, PydRedirect):
                yield from member.iter_wheel(content_prefix)
            elif isinstance(member, Package):
                yield from cls._iter_redirects(
                    member.members, prefix / member.name, content_prefix / member.name,
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
    members = ()

    def __init__(self, name, **options):
        self.name = name
        self.options = dict(**options)

    def write_member(self, project, group):
        group.switch_to("ItemGroup")
        project.add_item(self._ITEMNAME, self.name, **self.options)


class PydRedirect(File):
    r"""Represents a redirected extension module.

The name would normally be resolved within the packed DLL. However, for
.pyd files normally nested into a package, they need to be directed to
an adjacent file. The 'redirect_to' name will be loaded from the same
directory as the packed DLL using the default extension module loader.

If 'source' is provided, the module is automatically included in the
package. Additional options are applied as metadata to both the
redirect and the content (.pyd) file.
"""
    _ITEMNAME = "DllPackRedirect"
    members = ()

    options = {
        **File.options,
        "IncludeInSdist": False,
        "flatten": ".",
    }

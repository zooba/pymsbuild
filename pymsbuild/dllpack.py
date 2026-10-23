from pathlib import PurePath

from pymsbuild._types import *
from pymsbuild._types import _iter_check_paths


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

    def iter_check_wheel(self, state, prefix):
        name = self.options.get("TargetName") or self.name
        suffix = self.options.get("TargetExt")
        if suffix is None:
            suffix = (
                state.ext_suffix
                if getattr(state, "check_expand", False)
                else "$(DefaultExtSuffix)"
            )
        elif (
            getattr(state, "check_expand", False)
            and suffix in {"$(TargetExt)", "$(DefaultExtSuffix)"}
        ):
            suffix = state.ext_suffix
        yield state.expand_check_path(prefix / f"{name}{suffix}")
        source_dir = getattr(state, "_check_source_dir", PurePath()) / self.source
        yield from self._iter_redirects(
            state, self.members, prefix, prefix / self.name, source_dir,
        )

    @classmethod
    def _iter_redirects(cls, state, members, prefix, content_prefix, source_dir):
        for member in members:
            if isinstance(member, CProject):
                yield from _iter_check_paths(
                    (member,), "iter_check_wheel", state, prefix, source_dir,
                )
            elif isinstance(member, PydRedirect):
                yield from _iter_check_paths(
                    (member,), "iter_check_wheel", state, content_prefix, source_dir,
                )
            elif isinstance(member, Package):
                yield from cls._iter_redirects(
                    state, member.members, prefix / member.name, content_prefix / member.name,
                    source_dir / member.source,
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

import os
import sys

from pathlib import Path
from pymsbuild import CSourceFile, File, IncludeFile, Midl, PydFile


__all__ = [
    'WinUIExe',
    'XamlApp',
    'XamlPage',
]


TARGETS = Path(__file__).absolute().parent / "targets"


class XamlPage(File):
    _ITEMNAME = "Page"
    options = {
        "IncludeInSdist": True,
        "IncludeInLayout": False,
        "IncludeInWheel": False,
    }

    def generated_files(self):
        yield CSourceFile(self.name + ".cpp", DependentUpon=self.name)
        yield IncludeFile(self.name + ".h", DependentUpon=self.name)
        yield Midl(self.name.rpartition(".")[0] + ".idl", DependentUpon=self.name)


class XamlApp(XamlPage):
    _ITEMNAME = "ApplicationDefinition"


class WinUIExe(PydFile):
    class WinUIProps:
        members = ()
        name = "$WinUIExe.WinUIProps"
        def write_member(self, f, g):
            g.switch_to("PropertyGroup")
            f.add_property("_WinUITargetsPath", TARGETS)
            g.switch_to(None)
            f.add_import(f"$(_WinUITargetsPath){os.path.sep}winui.props")

    class WinUITargets:
        members = ()
        name = "$WinUIExe.WinUITargets"
        def write_member(self, f, g):
            g.switch_to(None)
            f.add_import(f"$(_WinUITargetsPath){os.path.sep}winui.targets")

    def __init__(self, name, *members, project_file=None, **kwargs):
        kwargs.setdefault("ConfigurationType", "Application")
        kwargs["TargetExt"] = ".exe"
        super().__init__(name, *members, project_file=project_file, **kwargs)
        extras = [m2 for m in self.members if isinstance(m, XamlPage) for m2 in m.generated_files()]
        self.insert(PydFile.GlobalProperties.name, self.WinUIProps(), offset=1)
        self.insert(PydFile.CppTargets.name, extras, range=True)
        self.members.append(self.WinUITargets())

    def init_PACKAGE(self, tag):
        if not tag:
            return
        # TODO: download packages from Nuget
        # TODO: download Python runtime

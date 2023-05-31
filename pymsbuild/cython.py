import os

from pathlib import Path
from pymsbuild._types import *

class CythonPydFile(PydFile):
    def __init__(self, name, *members, project_file=None, **kwargs):
        super().__init__(name, *members, project_file=project_file, **kwargs)
        self.members = [
            Property("BeforeBuildGenerateSourcesTargets", "Cythonize;$(BeforeBuildGenerateSourcesTargets)"),
            ItemDefinition("PyxCompile", TargetExt=".c", Dependencies=""),
            *self.members,
            LiteralXML(f'<Import Project="$(PyMsbuildTargets){os.path.sep}cython.targets" />'),
        ]


class PyxFile(File):
    _ITEMNAME = "PyxCompile"
    options = {
        "TargetExt": ".c",
        "IncludeInSdist": True,
        "IncludeInWheel": False,
    }


class CythonIncludeFile(File):
    _ITEMNAME = "CythonInclude"
    options = {
        "IncludeInSdist": True,
        "IncludeInWheel": False,
    }

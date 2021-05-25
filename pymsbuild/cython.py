from pathlib import Path
from pymsbuild._types import *

class CythonPydFile(PydFile):
    def __init__(self, name, *members, project_file=None, **kwargs):
        super().__init__(name, *members, project_file=project_file, **kwargs)
        self.members = [
            Property("BeforeBuildGenerateSourcesTargets", "Cythonize;$(BeforeBuildGenerateSourcesTargets)"),
            ItemDefinition("PyxCompile", TargetExt=".c", Dependencies=""),
            *self.members,
            LiteralXML('<Import Project="$(PyMsbuildTargets)/cython.targets" />'),
        ]


class PyxFile(File):
    _ITEMNAME = "PyxCompile"
    options = {"TargetExt": ".c"}


class CythonIncludeFile(File):
    _ITEMNAME = "CythonInclude"

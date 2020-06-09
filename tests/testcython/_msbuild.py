from pymsbuild import *
from pymsbuild.cython import *

PACKAGE = Package(
    "testcython",
    CythonPydFile("mod1",
        CythonIncludeFile("header.pxd"),
        PyxFile(
            "src.pyx",
            TargetExt=".cpp",
            ClPreprocessorDefinitions="SHOW=1",
            CythonPreprocessorDefinitions="SHOW=1",
        ),
    ),
)

DIST_INFO = {
    "Name": "testcython",
    "Version": "1.0.0",
}

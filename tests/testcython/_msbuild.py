from pymsbuild import *
from pymsbuild.cython import *

PACKAGE = Package(
    "testcython",
    CythonPydFile("mod1",
        PyxFile(
            "src.pyx",
            Dependencies="header.pxd",
            TargetExt=".cpp",
            PreprocessorDefinitions="SHOW=1",
        ),
    ),
)

DIST_INFO = {
    "Name": "testcython",
    "Version": "1.0.0",
}

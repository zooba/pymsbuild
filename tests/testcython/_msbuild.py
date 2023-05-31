from pymsbuild import *
from pymsbuild.cython import *

PACKAGE = Package(
    "testcython",
    CythonPydFile("mod1",
        IncludeFile("my_header.h"),
        CythonIncludeFile("header.pxd"),
        PyxFile(
            "src.pyx",
            TargetExt=".cpp",
            ClPreprocessorDefinitions="SHOW=1",
            CythonPreprocessorDefinitions="SHOW=1",
        ),
    ),
)

METADATA = {
    "Name": "testcython",
    "Version": "1.0.0",
}

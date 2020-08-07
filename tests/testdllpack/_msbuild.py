from pymsbuild import *
from pymsbuild.dllpack import *

PACKAGE = DllPackage(
    "testdllpack",
    PyFile("__init__.py"),
    PyFile("mod1.py"),
    PyFile("data.txt"),
    Package("sub",
        PyFile("mod2.py"),
        PyFile("data.txt"),
    ),
)

DIST_INFO = {
    "Name": "testdllpack",
    "Version": "1.0.0",
}

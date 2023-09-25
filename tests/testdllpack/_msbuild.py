from pymsbuild import *
from pymsbuild.dllpack import *

PACKAGE = DllPackage(
    "testdllpack",
    PyFile("__init__.py"),
    PyFile("mod1.py"),
    File("data.txt"),
    Package("sub",
        PyFile("__init__.py"),
        PyFile("mod2.py"),
        File("data.txt"),
    ),
    CSourceFile("extra.c"),
    CFunction("myfunc"),
    # Included as content, not code
    File("test-dllpack.py"),
    # Pretend this is a .pyd
    PydRedirect("pretend-pyd.txt", name="pretend.pyd", flatten="_"),
    PydRedirect("pretend-pyd.txt", name="pretend.pyd", flatten=True),
)

DIST_INFO = {
    "Name": "testdllpack",
    "Version": "1.0.0",
}

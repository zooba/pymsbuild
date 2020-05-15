from pymsbuild import *

Package(
    "testproject1",
    PydFile("mod1", CSourceFile("mod.c")),
    Package("sub",
        PydFile("mod2", CSourceFile("mod.c")),
        PyFile("sub_init.py", "__init__.py"),
    ),
).build(
    name="testproject1",
    version="1.0.0",
)

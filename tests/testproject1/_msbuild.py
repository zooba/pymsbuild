from pymsbuild import *

Package(
    "testproject1",
    PydFile("mod", CSourceFile("mod.c")),
).build(Metadata(
    name="testproject1",
    version="1.0.0",
))

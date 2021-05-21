from pymsbuild import *

PACKAGE = Package(
    "testproject1",
    PydFile("mod1", CSourceFile("mod.c")),
    Package("sub",
        PydFile("mod2", CSourceFile("mod.c")),
        PyFile("sub_init.py", "__init__.py"),
    ),
    LiteralXML("""<Target Name="ShowMessage" AfterTargets="Build">
  <Message Importance="high" Text="BUILD SUCCESS" />
</Target>"""),
)

METADATA = {
    "Name": "testproject1",
    "Version": "1.0.0",
}

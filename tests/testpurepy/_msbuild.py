from pymsbuild import *

PACKAGE = Package(
    "testproject1",
    PyFile("sub_init.py", "__init__.py"),
    Package("sub",
        PyFile("sub_init.py", "__init__.py"),
    ),
    LiteralXML("""<Target Name="ShowMessage" AfterTargets="Build">
  <Message Importance="high" Text="BUILD SUCCESS" />
</Target>"""),
)

DIST_INFO = {
    "Name": "testpurepy",
    "Version": "1.0.0",
}

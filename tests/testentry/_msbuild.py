from pymsbuild import *
from pymsbuild.dllpack import *
from pymsbuild.entrypoint import *

PACKAGE = Package(
    "testentry",
    Entrypoint(
        "run", "app", "main",
        VersionInfo(
            LegalCopyright="Copyright Me",
        ),
        Icon("Globe1.ico"),
        SearchPath("."),
        SearchPath("stdlib.zip"),
        SearchPath("files"),
    ),
    Package("files",
        DllPackage(
            "app",
            PyFile("app.py", name="__init__.py"),
        ),
    ),
)

METADATA = {
    "Name": "testentry",
    "Version": "1.0.0",
    "Author": "Test Author",
    "Summary": "testentry project",
}

def init_METADATA():
    for vi in PACKAGE.findall("*/VersionInfo"):
        vi.from_metadata(METADATA)

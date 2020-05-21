from pymsbuild import *

DIST_INFO = {
    "Metadata-Version": "1.1",
    "Name": "pymsbuild",
    "Version": "0.0.1",
    "Author": "Steve Dower",
    "Author-email": "steve.dower@python.org",
    "Home-page": "https://github.com/zooba/pymsbuild",
    "Summary": "The pymsbuild build backend.",
}

PACKAGES = [
    Package(
        "pymsbuild",
        PyFile("pymsbuild\\*.py"),
        File("pymsbuild\\targets\\*", name="targets\\*"),
    ),
]

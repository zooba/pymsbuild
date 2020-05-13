from pymsbuild import *

metadata = Metadata(
    name="pymsbuild",
    version="0.0.1",
    author="Steve Dower",
    author_email="steve.dower@python.org",
)

Package(
    "pymsbuild",
    metadata,
    PyFile.collect("pymsbuild\\*.py"),
    Package(
        "template",
        PyFile.collect("pymsbuild\\template\\*.py"),
        File.collect("pymsbuild\\template\\*.txt"),
        File.collect("pymsbuild\\template\\*.txt.in"),
    )
).build()
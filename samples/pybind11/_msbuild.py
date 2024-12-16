import os
from pymsbuild import *

METADATA = {
    "Metadata-Version": "2.2",
    "Name": "pybind11-sample",
    "Version": "1.0",
    "Summary": "TODO",
    "BuildWheelRequires": ["pybind11"],
}

# Add to as many projects as need to include pybind11.
# We will update with the real value in init_PACKAGE
PYBIND11_INCLUDE_DIR = ItemDefinition("ClCompile")


PACKAGE = Package(
    "pybind11_sample",
    PyFile("empty.py", name="__init__.py"),
    PydFile("example",
        PYBIND11_INCLUDE_DIR,
        CSourceFile("mod.cpp")
    ),
)


def init_PACKAGE(tag=None):
    # Only required pybind11 for wheel builds, so ensure 'tag' is not None
    if not tag:
        return

    import pybind11
    v = Prepend(f"{pybind11.get_include()};")
    PYBIND11_INCLUDE_DIR.options["AdditionalIncludeDirectories"] = v

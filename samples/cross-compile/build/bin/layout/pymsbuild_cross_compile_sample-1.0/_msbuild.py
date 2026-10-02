from pymsbuild import *

METADATA = {
    "Metadata-Version": "2.2",
    "Name": "pymsbuild-cross-compile-sample",
    "Version": "1.0",
    "Summary": "Cross-compilation properties sample",
}

BUILD_PROPERTIES = ItemDefinition(
    "ClCompile",
    PreprocessorDefinitions=(
        "TARGET_PYTHON_VERSION=$(TargetPythonVersion);"
        "PYTHON_TAG=$(PythonTag);"
        "ABI_TAG=$(AbiTag);"
        "PLATFORM_TAG=$(PlatformTag);"
        "CROSS_COMPILE=$(CrossCompile);"
        "%(PreprocessorDefinitions)"
    ),
)

PACKAGE = Package(
    "cross_compile_sample",
    PyFile("empty.py", "__init__.py"),
    PydFile("_native", BUILD_PROPERTIES, CSourceFile("native.c")),
)

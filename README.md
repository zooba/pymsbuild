# pymsbuild

This is a PEP 517 backend for building packages via MSBuild.

# Configuration file

The file is named `_msbuild.py`, and is executed by running `python -m pymsbuild`.

The package definition specifies all the files that end up in the released packages.

```python
from pymsbuild import *

PACKAGE = Package(
    "my_package",
    # Offset the package root from the _msbuild.py directory
    root="src",
    # Specify Python files directly...
    PyFile(r"my_package\__init__.py"),
    # ... or with a filename wildcard
    PyFile(r"my_package\*.py"),
    # Specify extension modules
    PydFile(
        "_accelerator",
        # Use a preconfigured project
        project_file=r"win32\accelerator.vcxproj",
    ),
    PydFile(
        "_accelerator2",
        # Include required files
        CSourceFile(r"win32\*.c"),
        CHeaderFile(r"win32\*.h"),
    ),
    # Subpackages nest inside other packages
    Package(
        "subpackage",
        PyFile(r"subpackage\*.py"),
    ),
)

# Metadata is specified raw, but an adjacent PKG_INFO file is preferred
DISTINFO = {
    "Metadata-Version": "1.1",
    "Name": "package",
    "Version": "1.0.0",
    "Author": "My Name",
    "Author-email": "myemail@example.com",
    "Classifier": [
        "Classifier :: 1",
        "Classifier :: 2",
    ]
}
```

# Usage

Rebuild the current project in-place.

```
python -m pymsbuild
```

Interactively generate the `_msbuild.py` file with project spec.

```
python -m pymsbuild init
```

Build the project and output an sdist

```
python -m pymsbuild sdist
```

Build the project and output a wheel

```
python -m pymsbuild wheel
```

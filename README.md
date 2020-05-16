# pymsbuild

This is a PEP 517 backend for building packages via MSBuild.

# Configuration file

The file is named `_msbuild.py`, and is executed by running `python -m pymsbuild`.

The package definition specifies all the files that end up in the released packages.

```python
from pymsbuild import *

metadata = Metadata(
    name="my-package",
    version="1.0.0",
    author="My Name",
    author_email="my.email@example.com",
    ...
)

p = Package(
    "my_package",
    # Offset the package root from the _msbuild.py directory
    root="src",
    # Specify Python files directly...
    PyFile(r"my_package\__init__.py"),
    # ... or 'collect' them with a filename wildcard
    PyFile.collect(r"my_package\*.py"),
    # Specify extension modules
    PydFile(
        "_accelerator",
        # Use a preconfigured project
        ProjectFile=r"win32\accelerator.vcxproj",
        # Include required files
        SourceFile=SourceFile.collect(r"win32\*"),
    ),
    # Subpackages nest inside other packages
    Package(
        "subpackage",
        PyFile.collect(r"subpackage\*.py"),
    ),
)

# Build sdist/wheel from a package+metadata
p.build(metadata)
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
python -m pymsbuild sdist [dir]
```

Build the project and output both sdist and wheel

```
python -m pymsbuild sdist [dir] wheel [dir]
```

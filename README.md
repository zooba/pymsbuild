# pymsbuild

This is a PEP 517 backend for building packages via MSBuild.

# Configuration file

The file is named `_msbuild.py`, and is imported as part of build or run directly. The package definition contains all the files that end up in the released packages.

```python
from pymsbuild import Metadata, Package, Project, PyFile, PydFile

p = Package(
    "my_package",
    Metadata(
        author="My Name",
        author_email="my.email@example.com",
        ...
    ),
    PyFile(r"my_package\__init__.py"),
    PydFile(
        "_accelerator",
        Project(r"win32\accelerator.vcxproj"),
    ),
    Package(
        "subpackage",
        PyFile.collect(r"subpackage\*.py"),
    ),
    source_root="src",
)

p.build()
```

# Usage

Rebuild the current project in-place.

```
python -m pymsbuild
python _msbuild.py
```

Interactively generate the `_msbuild.py` file with project spec.

```
python -m pymsbuild /init
```

Build the project and output an sdist

```
python -m pymsbuild /sdist [outputdir]
python _msbuild.py /sdist [outputdir]
```

Build the project and output both sdist and wheel

```
python -m pymsbuild /sdist [dir] /wheel [dir]
python _msbuild.py /sdist /wheel [dir]
```

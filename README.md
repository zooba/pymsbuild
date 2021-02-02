# pymsbuild

This is a PEP 517 backend for building packages via MSBuild.

# Configuration file

The file is named `_msbuild.py`, and is executed by running `python -m pymsbuild`.

The package definition specifies all the files that end up in the released packages.

```python
from pymsbuild import *

METADATA = {
    "Metadata-Version": "2.1",
    "Name": "package",
    "Version": "1.0.0",
    "Author": "My Name",
    "Author-email": "myemail@example.com",
    "Description": File("README.md"),
    "Description-Content-Type": "text/markdown",
    "Classifier": [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.9",
    ],
}

PACKAGE = Package(
    "my_package",
    PyFile(r"my_package\*.py"),
    PydFile(
        "_accelerator",
        CSourceFile(r"win32\*.c"),
        IncludeFile(r"win32\*.h"),
    ),
    Package(
        "subpackage",
        PyFile(r"subpackage\*.py"),
    ),
)
```

Note that subpackages _must_ be specified as a `Package` element, as the
nesting of `Package` elements determines the destination path. Otherwise you
will find all of your files flattened. Recursive wildcards, while partially
supported, are not going to work!

Also note that if you do not specify the `source=` named argument, all source
paths are relative to the configuration file.

# pyproject.toml file

You will need this file in order for `pip` to build your sdist, but otherwise it's
generally easier and faster to use `pymsbuild` directly.

```
[build-system]
requires = ["pymsbuild"]
build-backend = "pymsbuild"
```

# Usage

Rebuild the current project in-place.

```
python -m pymsbuild
```

Interactively generate the `_msbuild.py` file with project spec.
(Or at least, it will, once implemented.)

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

Clean any recent builds

```
python -m pymsbuild clean
```

# Advanced Examples

## Dynamic METADATA

Metadata may be dynamically generated, either on import or with the
`init_METADATA` function. This function is called and must either
return the metadata dict to use, or update `METADATA` directly.

However, if a `PKG-INFO` file is found adjacent to the configuration
file, it will be used verbatim. Sdist generation adds this file, so all
metadata is static from that point onward. `init_METADATA` is not
called in this case.

```python
from pymsbuild import *

METADATA = {
    "Metadata-Version": "2.1",
    "Name": "package",
    "Version": os.getenv("VERSION", "1.0.0"),
    "Author": "My Name",
    "Author-email": "myemail@example.com",
    "Description": File("README.md"),
    "Description-Content-Type": "text/markdown",
    "Classifier": [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.9",
    ],
}

def init_METADATA():
    if os.getenv("BUILD_BUILDNUMBER"):
        METADATA["Version"] = f"1.0.{os.getenv('BUILD_BUILDNUMBER', '')}"
    # Updated METADATA directly, so no need to return anything
```

## Separate packages

Packages are just Python objects, so they may be kept in variables and
used later. They also expose a `members` attribute, which is a list, so
that members can be added or inserted later.

After the entire module is executed, the package in `PACKAGE` is the
only one used to generate output.

```python
P1 = Package(
    "submodule",
    PyFile(r"src\submodule\__init__.py")
)

P2 = Package(
    "submodule_2",
    PyFile(r"src\submodule_2\__init__.py")
)

PACKAGE = Package("my_package", P1)
PACKAGE.members.append(P2)
```

## Dynamic packages

After import, if an `init_PACKAGE(tag=None)` function exists it will be
called with the intended platform tag. It must modify or return
`PACKAGE`. This function is called for in-place, sdist and wheel
generation, however, for sdists (and any scenario that should not
generate binaries), `tag` will be `None`. Otherwise, it will be a
string like `cp38-cp38-win32`.

```python
X64_ACCELERATOR = PydFile(
    "_my_package",
    CSourceFile(r"win32\*.c"),
    IncludeFile(r"win32\*.h"),
)

PACKAGE = Package(
    "my_package",
    PyFile(r"my_package\*.py"),
)

def init_PACKAGE(tag=None):
    if tag.endswith("-win_amd64"):
        PACKAGE.members.append(X64_ACCELERATOR)
```

## Source offsets

If you keep your source in a `src` folder (recommended), provide the
`source=` argument to `Package` in order to properly offset filenames.
Because it is a named argument, it must be provided last.

This is important for sdist generation and in-place builds, which need
to match package layout with source layout. Simply prefixing filename
patterns with the additional directory is not always sufficient.

Note that this will also offset subpackages, and that subpackages may
include additional `source` arguments. However, it only affects
sources, while the package name (the first argument) determines where
in the output the package will be located. In-place builds will create
new folders in your source tree if it does not match the final
structure.

```python
PACKAGE = Package(
    "my_package",
    PyFile(r"my_package\__init__.py"),
    source="src",
)
```

## Project file override

Both `Package` and `PydFile` types generate MSBuild project files and
execute them as part of build, including sdists. For highly customised
builds, this generation may be overridden completely by specifying the
`project_file` named argument. All members are then ignored.

By doing this, you take full responsibility for a valid build,
including providing a number of undocumented and unsupported targets.

Recommendations:
* lock your `pymsbuild` dependency to a specific version in `pyproject.toml`
* generate project files first and modify, rather than writing by hand
* read the `pymsbuild` source code, especially the `targets` folder
* consider contributing/requesting your feature

```python
PACKAGE = Package(
    "my_package",
    PydFile("_accelerator", project_file=r"src\accelerator.vcxproj")
)
```

## Compiler/linker arguments

Rather than overriding the entire project file, there are a number of
ways to inject arbitrary values into a project. These require
familiarity with MSBuild files and the toolsets you are building with.

The `Property` element inserts a `<PropertyGroup>` with the value you
specifiy at the position in the project the element appears.

Note that project files also interpret (most) named arguments as
properties, so the two properties shown here are equivalent.

```python
PYD = PydFile(
    "module",
    Property("WindowsSdkVersion", "10.0.18363.0"),
    WindowsSdkVersion="10.0.18363.0",
    ...
)
```

The `ItemDefinition` element inserts an `<ItemDefinitionGroup>` with
the type and metadata you specify at the position in the project the
element appears.

```python
PYD = PydFile(
    "module",
    ItemDefinition("ClCompile", PreprocessorDefinitions="Py_LIMITED_API"),
    ...
)
```

The `ConditionalValue` item may wrap any element value to add
conditions or concatenate the value. This may also be used on source
arguments for file elements.

```python
    ...
    Property("Arch", ConditionalValue("x86", condition="$(Platform) == 'Win32'")),
    Property("Arch", ConditionalValue("x64", if_empty=True)),
    ...
    ItemDefinition(
        "ClCompile",
        AdditionalIncludeDirectories=
            ConditionalValue(INCLUDES + ";", prepend=True),
        ProprocessorDefinitions=
            ConditionalValue(";Py_LIMETED_API", append=True),
    ),
    ...
```

`ConditionalValue` may also be used to dynamically update values in the
`init_PACKAGE` function, allowing you to keep the structure mostly
static but insert values from the current `METADATA` (which is fully
evaluated by the time `init_PACKAGE` is called).

```python
VER = ConditionalValue("1.0.0")

PYD = PydFile(
    "module",
    Property("Version", VER),
    CSourceFile(r"src\*.c"),
    IncludeFile(r"src\*.h"),
)

def init_PACKAGE(tag):
    VER.value = METADATA["Version"]
```

As a last resort, the `LiteralXml` element inserts plain text directly
into the generated file. It will be inserted as a child of the
top-level `Project` element.

```python
    ...
    LiteralXml("<Import Project='my_props.props' />"),
    ...
```

## Alternate config file

To use a configuration file other than `_msbuild.py`, specify the
`--config` (`-c`) argument or the `PYMSBUILD_CONFIG` environment
variable.

```powershell
python -m pymsbuild --config build-spec.py sdist
python -m pymsbuild --config build-spec.py wheel

# Alternatively
$env:PYMSBUILD_CONFIG = "build-spec.py"
python -m pymsbuild sdist wheel
```

Generated sdists will rename the configuration file back to
`_msbuild.py` in the package to ensure that builds work correctly.
There is no need to override the configuration file path when
building from sdists.

## Cross-compiling wheels

Cross compilation may be used by overriding the wheel tag or build
platform, as well as the source for Python's includes and libraries.
These must all be done using environment variables.

Note that it is also possible to override the wheel tag by adding a
`'WheelTag'` metadata value. However, while this will attempt to
update the MSBuild target platform automatically it will not be able to
select the correct Python libraries. For builds that do not directly
link to `python##.dll`, this is probably fine.

You can also override the platform toolset with the `'PlatformToolset'`
metadata value, for scenarios where this information ought to be
included in an sdist.

The set of valid platforms for auto-generated `.pyd` project files are
hard-coded into `pymsbuild` and are currently `Win32`, `x64`, `ARM` and
`ARM64`. Custom project files may use whatever they like.

```powershell
# Directly specify the resulting wheel tag
$env:PYMSBUILD_WHEEL_TAG = "py38-cp38-win_arm64"

# Directly override the MSBuild platform.
# In this example, the wheel tag would have been sufficient
$env:PYMSBUILD_PLATFORM = "ARM64"

# Specify the paths to ARM64 headers and libs
$env:PYTHON_INCLUDES = "$pyarm64\Include"
$env:PYTHON_LIBS = "$pyarm64\libs"

# Alternatively, just specify the prefix directory
$env:PYTHON_PREFIX = $pyarm64

# If necessary, specify an alternate C++ toolset
$env:PLATFORMTOOLSET = "Intel C++ Compiler 19.1"
```

Note that compiled modules typically include an ABI tag in the filename
that will require overriding. To do this based on the already-specified
wheel tag, use an `init_PACKAGE` function that maps to your desired
suffixes.

```python
def init_PACKAGE(wheel_tag=None):
    ext = {
        "py36-cp36-win_amd64": ".cp36-win_amd64.pyd",
        "py37-cp37-win_amd64": ".cp37-win_amd64.pyd",
        "py38-cp38-win_amd64": ".cp38-win_amd64.pyd",
        "py39-cp39-win_amd64": ".cp39-win_amd64.pyd",
    }.get(wheel_tag, ".pyd")

    for p in PACKAGE:
        if isinstance(p, PydFile):
            p.options["TargetExt"] = ext
```


## Cython

Cython support is available from the `pymsbuild.cython` module.

```python
from pymsbuild import PydFile, ItemDefinition
from pymsbuild.cython import CythonIncludeFile, CythonPydFile, PyxFile

PACKAGE = CythonPydFile(
    "cython_module",
    ItemDefinition("PyxCompile", IncludeDirs=PYD_INCLUDES),
    CythonIncludeFile("mod.pxd"),
    PyxFile("mod.pyx"),
)
```

The `CythonPydFile` type derives from the regular `PydFile` and also
generates a C++ project, so all options that would be available there may
also be used.

The `PyxCompile.IncludeDirs` metadata specifies search paths for Cython
headers (`*.pxd`). You may also need to specify
`ClCompile.AdditionalIncludeDirectories` for any C/C++ headers.


## DLL Packing

**Experimental.**

DLL Packing is a way to compile a complete Python package (`.py` source
and resource files) into a Windows DLL. It is fundamentally equivalent
to packing in a ZIP file, except that additional native code may also be
included (though not an entire native module), and the whole file may be
cryptographically signed and validated by the operating system.

`DllPackage` is a drop-in substitute for the `Package` type.

```python
from pymsbuild import *
from pymsbuild.dllpack import *

PACKAGE = DllPackage(
    "packed_package",
    PyFile("__init__.py"),
    File("data.txt"),
    ...
)
```

`DllPackage` is a subclass of `PydFile`, and so all logic or elements
by that type are also available. `ClCompile` elements will be compiled
and linked into the output and functions may be exposed in the root of
the package using the `Function` element.

```c
// extra.c

PyObject *my_func(PyObject *, PyObject *args, PyObject **kwargs) {
    ...
}
```

```python
PACKAGE = DllPackage(
    "packed_package",
    PyFile("__init__.py"),
    CSourceFile("extra.c"),
    CFunction("my_func"),
    ...
)
```

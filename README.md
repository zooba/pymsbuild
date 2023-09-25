# pymsbuild

This is a PEP 517 backend for building packages via MSBuild or `dotnet build`.

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
will find all of your files flattened. Recursive wildcards are supported, however,
be aware that it is not always intuitive how the paths are going to be remapped.

Also note that without a `source=` named argument, all source paths are
relative to the configuration file.

# pyproject.toml file

You will need this file in order for `pip` to build your sdist, but otherwise it's
generally easier and faster to use `pymsbuild` directly.

```
[build-system]
requires = ["pymsbuild"]
build-backend = "pymsbuild"
```

On Windows, a [Visual Studio](https://www.visualstudio.com) installation will be
required. It will be automatically detected, or the path to MSBuild can be
provided as the `MSBUILD` environment variable.

On other platforms, the [.NET SDK](https://dotnet.microsoft.com/download) will be
required. The `dotnet` command must be available on `PATH` or specified as the
`MSBUILD` environment variable.

If you have additional requirements for building either sdist or wheels, add
them as `BuildSdistRequires` or `BuildWheelRequires` values in `METADATA`. They
will be parsed after `init_METADATA` and/or `init_PACKAGE` have been called, so
may be modified by these functions.

# Usage

## Rebuild the current project in-place.

```
python -m pymsbuild
```

## Interactively generate the `_msbuild.py` file with project spec.

(Or at least, it will, once implemented.)

```
python -m pymsbuild init
```

## Build the project and output an sdist

```
python -m pymsbuild sdist
```

Output is put into `dist` by default, but can be overridden with `--dist-dir`
(`-d`).

## Build the project and output a wheel

```
python -m pymsbuild wheel
```

Output is put into `dist` by default, but can be overridden with `--dist-dir`
(`-d`).

## Clean any recent builds

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

## Wildcard handling

Files can be added recursively using wildcard operators. These are
evaluated at generation time by `pymsbuild` and not by MSBuild/
`dotnet build`, as it allows greater control over target names.

```python
PACKAGE = Package(
    "my_package",
    # All .py files, relative to the 'src' directory
    PyFile(r"**\*.py"),
    # All license files, if any, with path separators converted to '-'
    File(r"**\license*", flatten="-", allow_none=True),
    # All .bin files from all data directories, moved to the root
    File(r"**\data\*.bin", flatten=True),
    source="src"
)
```

`flatten` specifies the string sequence to replace path separators in
the name. Passing `True` indicates that only the file name should be
retained.

`allow_none` merely suppresses a build-time error when the wildcard
fails to match any files. This is usually an important problem, and
should be suppressed with care.

The `flatten` and `allow_none` properties are not written to the build
file. However, they are case-sensitive while MSBuild is not, so the
capitalised versions will be ignored for this processing and passed
through.

Specifying the `Name` metadata (as opposed to `name`, which is a
keyword argument) will override the destination name of every matched
file. This is applied before flattening, and so will preserve the
relative path in whatever form is specified by `flatten`. To bypass
this additional processing and use the name as an MSBuild literal,
wrap it in a `ConditionalValue` with no condition:

```python
PACKAGE = Package(
    "my_package",
    File("**/*.dat", Name=ConditionalValue("%(Filename)-1.dat")),
)
```

For more complex transforms on filename, we recommend using the
`init_PACKAGE` function described below.

## Dynamic packages

After import, if an `init_PACKAGE(tag=None)` function exists it will be
called with the intended platform tag. It must modify or return
`PACKAGE`. This function is called for in-place, sdist and wheel
generation, however, for sdists (and any scenario that should not
generate binaries), `tag` will be `None`. Otherwise, it will be a
string like `cp38-cp38-win32`.

```python
PACKAGE = Package(
    "my_package",
    PyFile(r"my_package\*.py"),
)

def init_PACKAGE(tag=None):
    if tag and tag.endswith("-win_amd64"):
        data_file = generate_data_amd64()
        PACKAGE.members.append(File(data_file))
```

Note that all files to be included in an sdist must be referenced when
`tag` is `None`. Conditional compilation is best performed using conditions
in the package elements, rather than using `init_PACKAGE`. However, if you
are going to use `init_PACKAGE`, you should _remove_ elements rather than
adding them if they should be included in your sdist.

Files added as part of a wildcard can be removed by adding a `RemoveFile`
element. These may be added dynamically during `init_PACKAGE`, and must
appear after the element that included the files.

```python
PACKAGE = Package(
    "my_package",
    PyFile(r"my_package\*.py"),
    RemoveFile(PyFile, r"my_package\_internal.py"),
)
```

To exclude files from a wildcard in the first place, chain the `.excluding`
method on the original element. The pattern will be evaluated in exactly the
same way as the inclusion pattern, and any paths that match will be omitted.

```python
PACKAGE = Package(
    "my_package",
    PyFile(r"my_package\*.py").excluding("my_package\internal*.py"),
)
```

Alternatively, a condition may be added to the file pattern to only include
files matching MSBuild style conditions. Because these will be applied to
item groups, the `%()` metadata syntax should be used to access information
for the element being added. Either the `.if_` method or the
`ConditionalValue` wrapper may be used.

```python
PACKAGE = Package(
    "my_package",
    PyFile(r"my_package\*.py").if_("%(Filename) != '_internal'"),
    File(ConditionalValue("*.txt", condition="%(Filename.StartsWith(`internal`))")),
)
```

Package members can be located during the dynamic stage using the `find` and
`findall` functions. These take a path of member identifiers (typically their
name property) and will return those that match.

```python
PACKAGE = Package(
    "my_package",
    Package("sub1", File("license.txt")),
    Package("sub2", File("license.txt")),
)

def init_PACKAGE(tag=None):
    for e in PACKAGE.findall("sub*/license.txt"):
        e.name = "LICENSE"
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
            ConditionalValue(";Py_LIMITED_API", append=True),
    ),
    ...
```

The `Prepend` shortcut may be used to reduce the amount of text for
property values. Remember to include the appropriate separator.

```python
    ...
    ItemDefinition(
        "ClCompile",
        AdditionalIncludeDirectories=Prepend(INCLUDES + ";"),
        ProprocessorDefinitions=Prepend("Py_LIMITED_API;"),
    ),
    ...
```
`ConditionalValue` may also be used to dynamically update values in the
`init_PACKAGE` function, allowing you to keep the structure mostly
static but insert values from the current `METADATA` (which is fully
evaluated by the time `init_PACKAGE` is called). This saves having to
access internal members of other types in order to replace literal
values.

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

## Version info for DLLs/PYDs

To embed version info into a compiled extension module (on Windows),
add a `VersionInfo` element into the `PydFile`. All the fields from
https://learn.microsoft.com/en-us/windows/win32/menurc/versioninfo-resource
are available, using the names as shown in the tables (e.g.
`FILEVERSION` for the `'1,0,0,0'` fields and `FileVersion` for the string
table entry).

The recommended usage is to add a default instance into your project and then
use 'init_METADATA' to find it again and update the final metadata.

```
PACKAGE = Package(
    "package",
    PydFile("mod1", VersionInfo()),
    PydFile("mod2", VersionInfo()),
)

def init_METADATA():
    METADATA["Version"] = calculate_current_version()
    for vi in PACKAGE.findall("*/VersionInfo"):
        vi.from_metadata(METADATA)
```

`from_metadata` will fill in any empty fields from the set of metadata that is
passed in.

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

Note that this is different from the `PYMSBUILD_CONFIGURATION`
variable, which is used to select debug/release settings for compiled
modules.

## Cross-compiling wheels

Cross compilation may be used by overriding the wheel tag, ABI tag,
or build platform, as well as the source for Python's includes and
libraries. These all use environment variables, to ensure that the
same setting can flow through a package installer's own process.

It is also possible to permanently override the wheel tag by adding
a `'WheelTag'` metadata value, or the ABI tag by adding an `'AbiTag'`
metadata value.

The wheel tag is used for the generated wheel file, and to fill in a
missing ABI tag and platform.

The ABI tag is used for any native extension modules, and to fill in
a missing platform.

Any `*` elements in the wheel tag are filled in from other locations.
For example, specifying `*-none-any` will infer the interpreter field
from the current runtime, whil `py3-none-*` will infer the platform
from the currnet system (or a specific ABI tag).

The platform is used to determine the MSBuild target platform. It
cannot yet automatically select the correct Python libraries, and so
you will need to set `PYTHON_INCLUDES` and `PYTHON_LIBS` (or with a
`PYMSBULID_` prefix) environment variables as well to locate the
correct files.

You can override the platform toolset with the `'PlatformToolset'`
metadata value, for scenarios where this information ought to be
included in an sdist.

The set of valid platforms for auto-generated `.pyd` project files are
hard-coded into `pymsbuild` and are currently `Win32`, `x64`, `ARM` and
`ARM64`. Custom project files may use whatever they like. These
platforms should behave properly cross-platform, though in general only
`x64` and `ARM64` are supported.

```powershell
# Directly specify the resulting wheel tag
# This is used for the wheel filename/metadata
$env:PYMSBUILD_WHEEL_TAG = "py38-cp38-win_arm64"

# Directly set the ABI tag (or else taken from wheel tag)
# This is used for extension module filenames
$env:PYMSBUILD_ABI_TAG = "cp38-win_arm64"

# Specify the Python platform (or else taken from ABI tag)
# This is used for MSBuild options
$env:PYMSBUILD_PLATFORM = "win_arm64"

# Specify the paths to ARM64 headers and libs
$env:PYTHON_INCLUDES = "$pyarm64\Include"
$env:PYTHON_LIBS = "$pyarm64\libs"

# If necessary, specify an alternate C++ toolset
$env:PLATFORMTOOLSET = "Intel C++ Compiler 19.1"
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


## Two-Step Builds

By default, the `sdist` and `wheel` commands will perform the entire
process in a single invocation. However, sometimes there are build steps
that must be manually performed between compilation and packaging.

To run the build in two stages, invoke as normal, but add the
`--layout-dir` argument followed by a directory. The package will be
laid out in this directory so that you can perform any extra processing.

Later, use the `pack` command and specify the `--layout-dir` again. If
you have added new files into the layout directory, specify each with an
`--add` option (filenames starting with `@` are treated as
newline-separated, UTF-8 encoded text files listing each new file). These
paths may be absolute or relative to the layout directory, but only files
located within the layout directory will be included.

All other options are retained from the original invocation.

```
python -m pymsbuild sdist --layout-dir tmp

# Generate additional metadata in tmp/EXTRA.txt

python -m pymsbuild pack --layout-dir tmp --add tmp/EXTRA.txt
```

# Experimental Features

## DLL Packing

**Experimental. Windows only.**

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

### Nested extension modules

To allow referencing other extension modules that would normally be
nested within the module, add `DllRedirect` element and include the
extension module adjacent to your packed DLL. The filename does not
have to match the original name, as it will be passed directly to the
module loader.

```python
PACKAGE = DllPackage(
    "packed",
    DllRedirect("packed.nested", "packed-nested.pyd"),
    ...
)
```

### Encryption

To encrypt your content using symmetric AES encryption, provide the
name of the environment variable holding your key as the
`EncryptionKeyVariable` option. The key will need to be a valid size
(usually 16, 24 or 32 bytes) when encoded to UTF-8 or decoded from
base 64. Base 64 keys should start with `base64:`.

The same variable will need to be set when importing the module. It is
your responsibility to protect the key! The benefit of this encryption
is best realised when you avoid storing the key to disk. That way, an
attacker who steals a copy of your module is unlikely to have access to
the key. An attacker with access to a running copy of your module will
be able to easily extract the key.

```python
PACKAGE = DllPackage(
    "package",
    ...,
    EncryptionKeyVariable="MY_KEY_VARIABLE"
)
```

```powershell
> $env:MY_KEY_VARIABLE="base64:MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
> python -m pymsbuild
> del env:\MY_KEY_VARIABLE
> python -c "import package"
ImportError: Module cannot be decrypted
```

## Cross-platform builds

**Experimental.**

With the [.NET SDK](https://dotnet.microsoft.com/download) installed,
`pymsbuild` is able to run builds on platforms other than Windows.
The `dotnet` command must be available on `PATH` or specified as the
`MSBUILD` environment variable.

In general, no platform-specific modifications to a build script are
required. Cython and pyd builds are transparently mapped to the target
system. To run build-time actions for specific platforms, add them to
`init_PACKAGE` and check the tag argument to determine the target
platform.

When building native components on POSIX, a `python3-config` script is
needed to determine compilation options. By default, only the location
adjacent to the running interpreter is checked. This may be overridden
by setting the `PYTHON_CONFIG` variable to the preferred command.
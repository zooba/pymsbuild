import importlib.resources
import itertools
import re
import sys

from . import PYMSBUILD_REQUIRES_SPEC

from pathlib import PurePosixPath

# importlib.resources has no feature detection, so we have to assume that
# they'll stick to CPython versions.
if sys.version_info[:2] >= (3, 11):
    TEMPLATE = (importlib.resources.files("pymsbuild") / "_msbuild.py.in").read_text()
    TOML_TEMPLATE = (importlib.resources.files("pymsbuild") / "pyproject.toml.in").read_text()
else:
    TEMPLATE = importlib.resources.read_text("pymsbuild", "_msbuild.py.in")
    TOML_TEMPLATE = importlib.resources.read_text("pymsbuild", "pyproject.toml.in")

C_PREPROC_BLURB = """
# Need to set preprocessor variables or include dirs? Use a ClCompile item definition
#ItemDefinition(
#    "ClCompile",
#    PreprocessorDefinitions=Prepend("NAME=1;"),
#    AdditionalIncludeDirectories=Prepend("PATH;"),
#),
# Need to set linker options or directories? Use a Link item definition
#ItemDefinition(
#    "Link",
#    AdditionalDependencies=Prepend("kernel32.lib;"),
#    AdditionalLibraryDirectories=Prepend("PATH;"),
#),
""".strip().splitlines()

def _generate_module(root, offset=None, build_requires=None, _indent="    ", _root=None):
    if not root:
        return
    if not _root:
        _root = root

    def _p(pattern):
        parent = root.parent
        if offset:
            parent /= offset
        return str(PurePosixPath(root.relative_to(parent) / pattern))

    yield f'{_indent}{root.name!r},'
    yield f'{_indent}PyFile({_p("*.py")!r}),'
    any_pyi = False
    for d in root.iterdir():
        if (d / "__init__.py").is_file():
            yield f''
            yield f'{_indent}# Discovered from {d.relative_to(_root)}'
            yield f'{_indent}Package('
            yield from _generate_module(d, build_requires=build_requires, _indent=_indent + '    ', _root=_root)
            yield f'{_indent}),'
        elif d.is_file():
            if d.match("*.pyx"):
                if "Cython" not in build_requires:
                    build_requires.append("Cython")
                yield f''
                yield f'{_indent}# Discovered from {d.relative_to(_root)}'
                yield f'{_indent}CythonPydFile('
                yield f'{_indent}    {d.stem!r},'
                yield from (f'{_indent}    {i}' for i in C_PREPROC_BLURB)
                yield f'{_indent}    PyxFile({_p(d.name)!r}),'
                if any(root.glob("*.pxi")):
                    yield f'{_indent}    CythonHeaderFile({_p("*.pxi")!r}),'
                yield f'{_indent}),'
            elif d.match("*.c") or d.match("*.cpp"):
                yield f''
                yield f'{_indent}# Discovered from {d.relative_to(_root)}'
                yield f'{_indent}PydFile('
                yield f'{_indent}    {d.stem!r},'
                yield from (f'{_indent}    {i}' for i in C_PREPROC_BLURB)
                yield f'{_indent}    CSourceFile({_p(d.name)!r}),'
                if any(root.glob("*.h")):
                    yield f'{_indent}    HeaderFile({_p("*.h")!r}),'
                if any(root.glob("*.hpp")):
                    yield f'{_indent}    HeaderFile({_p("*.hpp")!r}),'
                yield f'{_indent}),'
            elif d.match("*.pyi"):
                any_pyi = True
    if any_pyi:
        yield f'{_indent}File({_p("*.pyi")!r}),'
    if offset:
        yield f'{_indent}source={offset!r},'


def run(build_state, config_name="_msbuild.py"):
    root = build_state.source_dir
    force = build_state.force

    config_file = root / (build_state.config_file or config_name)

    if config_file.is_file():
        if force:
            config_file.unlink()
        else:
            raise RuntimeError(f"{config_file} already exists. Delete the file before using 'init'")

    substitutions = {}
    build_requires = [PYMSBUILD_REQUIRES_SPEC]

    project = root
    offset = None
    if (root / "src").is_dir():
        offset = "src"
        project = root / "src"
    modules = [d for d in project.iterdir() if (d / "__main__.py").is_file()]
    if not modules:
        modules = [d for d in project.iterdir() if (d / "__init__.py").is_file()]
    if len(modules) == 1:
        project = modules[0]
    elif len(modules) > 1:
        project = max(modules, key=lambda m: len(list(m.glob("*.py"))))
    else:
        project = None
    substitutions["NAME"] = project.name if project else "package"

    substitutions["PACKAGE"] = "\n".join([
        "PACKAGE = Package(",
        *_generate_module(
            project,
            offset,
            build_requires,
            _root=project.parent if project else None,
        ),
        ")",
    ])

    substitutions["BUILD_REQUIRES"] = repr(build_requires)

    substitutions["GIT"] = "TODO"
    substitutions["GITISSUES"] = "TODO"

    cfg = root / ".git/config"
    if cfg.is_file():
        with cfg.open("r", encoding="utf-8-sig") as f:
            for line in f:
                if line.strip().startswith("[remote"):
                    for line in f:
                        m = re.match(r"\s*url\s*=\s*(.+)$", line)
                        if m:
                            substitutions["GIT"] = m.group(1)
                            substitutions["GITISSUES"] = f"{m.group(1)}/issues"
                            break
                    break

    code = re.sub(r"\<(\w+)\>", lambda m: substitutions.get(m.group(1)), TEMPLATE)
    with open(config_file, "w", encoding="utf-8") as f:
        print(code, file=f, end="")
    print("Wrote", root / config_file)

    toml = re.sub(r"\<(\w+)\>", lambda m: substitutions.get(m.group(1)), TOML_TEMPLATE)
    pyproject = config_file.parent / "pyproject.toml"
    if pyproject.is_file():
        if force:
            pyproject.unlink()
        else:
            pyproject = pyproject.parent / "pyproject.toml.txt"
            count = 1
            while pyproject.is_file():
                pyproject = pyproject.parent / f"pyproject.toml.{count}.txt"
                count += 1
            print("NOTE: pyproject.toml exists, so wrote recommended settings to", pyproject, file=sys.stderr)
    with open(pyproject, "w", encoding="utf-8") as f:
        print(toml, file=f, end="")
    print("Wrote", pyproject)

import importlib.resources
import re
import sys


TEMPLATE = importlib.resources.read_text("pymsbuild", "_msbuild.py.in")


def _generate_module(root, offset=None, _indent="    "):
    if not root:
        return
    yield f'{_indent}{root.name!r},'
    yield f'{_indent}PyFile("*.py"),'
    for d in root.iterdir():
        if (d / "__init__.py").is_file():
            yield f'{_indent}Package('
            yield from _generate_module(d, _indent=_indent + '    ')
            yield f'{_indent}),'
    if offset:
        yield f'{_indent}source={offset!r},'


def run(root, config_name="_msbuild.py"):
    if (root / config_name).is_file():
        print(config_name, "already exists. Delete the file before using 'init'", file=sys.stderr)
        return

    substitutions = {}

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
        *_generate_module(project),
        ")",
    ])

    code = re.sub(r"\<(\w+)\>", lambda m: substitutions.get(m.group(1)), TEMPLATE)
    with open(root / config_name, "w", encoding="utf-8") as f:
        print(code, file=f, end="")

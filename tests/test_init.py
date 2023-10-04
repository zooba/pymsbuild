import ast
import os
import pytest
import sys

from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pymsbuild
from pymsbuild._init import run

@pytest.fixture
def init_project(inittestprojects, tmp_path):
    def do_init(name):
        output = tmp_path / "_msbuild.py"
        run(inittestprojects / name, output)
        assert output.is_file()
        pyproj = output.parent / "pyproject.toml"
        assert pyproj.is_file()
        return output.read_text(encoding="utf-8"), pyproj.read_text(encoding="utf-8")
    return do_init

class Validator(ast.NodeVisitor):
    def __init__(self, metadata, package):
        self.metadata = metadata
        self.package = package
        self._package = []

    def visit_Assign(self, n):
        if isinstance(n.targets[0], ast.Name):
            if n.targets[0].id == "METADATA":
                return self.visit_METADATA(n.value)
            elif n.targets[0].id == "PACKAGE":
                self.visit_PACKAGE(n.value, "")
                assert set(self._package) >= set(self.package)
                return

    def visit_METADATA(self, n):
        assert isinstance(n, ast.Dict)
        for k, v in zip(n.keys, n.values):
            assert isinstance(k, ast.Str)
            try:
                expect = self.metadata[k.s]
            except LookupError:
                pass
            else:
                assert isinstance(v, ast.Str)
                assert expect == v.s

    def visit_PACKAGE(self, n, path):
        assert isinstance(n, ast.Call)
        assert isinstance(n.args[0], ast.Str)
        name = n.args[0].s
        path = f"{path}/{n.func.id}[{name}]"
        self._package.append(path)
        for a in n.args[1:]:
            self.visit_PACKAGE(a, path)


def test_init_1(init_project):
    content, pyproj = init_project("proj1")
    print(content)
    print()
    tree = ast.parse(content)
    Validator({
        "Name": "module",
        "Author": "TODO",
    }, [
        "/Package[module]",
        "/Package[module]/PyFile[module/*.py]",
        "/Package[module]/CythonPydFile[cythonmod]",
        "/Package[module]/Package[subpackage]/PydFile[mod2]",
    ]).visit(tree)

    print(pyproj)
    if pymsbuild.__version__ == '%VERSION%':
        assert "'pymsbuild'" in pyproj
    else:
        assert "pymsbuild>=" in pyproj
    assert "Cython" in pyproj

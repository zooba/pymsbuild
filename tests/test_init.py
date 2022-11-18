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

def test_init_1(init_project):
    content, pyproj = init_project("proj1")
    print(content)
    assert '"Name": "module"' in content
    assert 'Package(' in content
    assert 'PydFile(' in content
    assert 'CythonPydFile(' in content
    assert "'module'" in content
    assert "'subpackage'" in content
    print(pyproj)
    assert "pymsbuild>=" in pyproj
    assert "Cython" in pyproj

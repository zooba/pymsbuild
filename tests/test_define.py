import os
import pytest
import sys

from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pymsbuild
import pymsbuild._generate as G
import pymsbuild._types as T

def test_iterable_project():
    package = T.Package("package",
        T.PyFile("empty.py", "__init__.py"),
        T.PydFile("mod",
            T.CSourceFile("mod.c"),
            TargetExt=".pyd",
        ),
    )
    assert [
        T.PyFile,
        T.PydFile,
        T.PydFile.GlobalProperties,
        T.PydFile.DefaultToolsetImports,
        T.PydFile.ConfigurationProperties,
        T.PydFile.ToolsetImports,
        T.CSourceFile,
        T.PydFile.ToolsetTargets,
    ] == [type(p) for p in package]


def test_find():
    package = T.Package("package",
        T.PyFile("empty.py", "__init__.py"),
        T.PydFile("mod",
            T.CSourceFile("mod.c"),
            TargetExt=".pyd",
        ),
    )
    assert [T.PydFile] == [type(p) for p in package.findall("mod")]
    assert [] == [type(p) for p in package.findall("mod.c")]
    assert [T.CSourceFile] == [type(p) for p in package.findall("mod/mod.c")]
    assert [T.CSourceFile] == [type(p) for p in package.findall("*/mod.c")]
    assert [T.CSourceFile] == [type(p) for p in package.findall("mod/*.c")]
    assert [T.PyFile] == [type(p) for p in package.findall("*.*")]
    assert [T.CSourceFile] == [type(p) for p in package.findall("*/*.*")]
    assert [T.PyFile, T.CSourceFile] == [type(p) for p in package.findall("**/*.*")]

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
    assert [T.PyFile, T.PydFile, T.CSourceFile] == [type(p) for p in package]

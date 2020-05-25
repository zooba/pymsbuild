import os
import pytest
import sys

from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pymsbuild
import pymsbuild._generate as G
import pymsbuild._types as T
from pymsbuild._build import locate as locate_msbuild

# Avoid calling locate() for each test
os.environ["MSBUILD"] = str(locate_msbuild())

def test_build_sdist(tmp_path, testdata):
    p = T.Package("package",
        T.PyFile(testdata / "empty.py", "__init__.py"),
        T.PydFile("mod",
            T.CSourceFile(testdata / "mod.c"),
        ),
    )
    G.generate_distinfo({"Name": "package", "Version": "1.0"}, tmp_path / "obj", testdata)
    pf = G.generate(p, tmp_path / "obj", testdata)
    pymsbuild.build(pf, target="BuildSdist", OutDir=tmp_path / "out")

    files = [p.relative_to(tmp_path) for p in Path(tmp_path).rglob("out\\**\\*")]
    assert files
    assert {f.name for f in files} == {"empty.py", "mod.c", "pyproject.toml", "_msbuild.py", "PKG-INFO"}

    pymsbuild.build(pf, target="Clean", OutDir=tmp_path / "out")
    files = [p.relative_to(tmp_path) for p in Path(tmp_path).rglob("out\\**\\*")]
    assert not files

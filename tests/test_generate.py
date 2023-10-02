import os
import pytest
import sys

from xml.etree import ElementTree
from pathlib import Path, PurePath

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pymsbuild
import pymsbuild._generate as G
import pymsbuild._types as T

FILE_TYPES = [
    ("Content", T.File),
    ("Content", T.PyFile),
    ("None", T.SourceFile),
    ("ClCompile", T.CSourceFile),
    ("ClInclude", T.IncludeFile),
]


@pytest.mark.parametrize("itemkind, ftype", FILE_TYPES)
def test_file_types(itemkind, ftype):
    f = ftype("testdata/f.py", opt1=1)
    assert f._ITEMNAME == itemkind
    assert f.source == PurePath("testdata/f.py")
    assert f.name == "f.py"
    assert f.options["opt1"] == 1


class ProjectFileChecker:
    def __init__(self, projfile):
        print(projfile)
        print(projfile.read_text())
        self.root = ElementTree.parse(projfile)
        self.ns = {
            "x": self.root.getroot().tag.partition("}")[0][1:]
        }

    def get(self, xpath):
        xpath = xpath.replace("{SEP}", os.path.sep)
        return self.root.find(xpath, namespaces=self.ns)

    def getall(self, xpath, attr=None):
        xpath = xpath.replace("{SEP}", os.path.sep)
        f = self.root.findall(xpath, namespaces=self.ns)
        if attr:
            return (i.get(attr) for i in f)
        return f


def test_pyd_generation(tmp_path):
    p = T.PydFile("package",
        T.CSourceFile("m.c"),
        T.IncludeFile("m.h"),
        T.SourceFile("m.txt"),
        TargetExt=".pyd",
    )
    pf = ProjectFileChecker(G._generate_pyd(p, tmp_path, tmp_path))
    targets = Path(pf.get("./x:PropertyGroup[@Label='Globals']/x:PyMsbuildTargets").text)
    assert (targets / "package.targets").is_file()
    assert (targets / "pyd.targets").is_file()

    clcompile = pf.get("./x:ItemGroup/x:ClCompile[@Include]")
    assert Path(tmp_path / "m.c") == Path(clcompile.get("Include"))
    clinclude = pf.get("./x:ItemGroup/x:ClInclude[@Include]")
    assert Path(tmp_path / "m.h") == Path(clinclude.get("Include"))
    none = pf.get("./x:ItemGroup/x:None[@Include]")
    assert Path(tmp_path / "m.txt") == Path(none.get("Include"))

    assert pf.get("./x:Import[@Project='$(PyMsbuildTargets){SEP}common.targets']") is not None
    assert pf.get("./x:Import[@Project='$(PyMsbuildTargets){SEP}pyd.targets']") is not None


def test_package_generation(tmp_path):
    p = T.Package("package",
        T.PyFile("m.py", "__init__.py"),
        T.SourceFile("m.txt"),
        T.Package("subpackage",
            T.PyFile("__init__.py"),
            T.Package("subpackage",
                T.PyFile("__init__.py"),
            )
        )
    )
    pf = ProjectFileChecker(G.generate(p, tmp_path, tmp_path))
    targets = Path(pf.get("./x:PropertyGroup[@Label='Globals']/x:PyMsbuildTargets").text)
    assert (targets / "package.targets").is_file()

    sdist_md = pf.getall("./x:ItemGroup[@Label='Sdist metadata']/x:Sdist", "Include")
    assert {PurePath(i).name for i in sdist_md} == {"pyproject.toml", "PKG-INFO", "_msbuild.py"}
    sdist_md = pf.getall("./x:ItemGroup[@Label='Sdist metadata']/x:Sdist/x:RelativeSource")
    assert {i.text for i in sdist_md} == {"pyproject.toml", "PKG-INFO", "_msbuild.py"}

    files = pf.getall("./x:ItemGroup/x:Content/x:Name")
    assert {i.text.replace('\\', '/') for i in files} == {
        "package/__init__.py",
        "package/subpackage/__init__.py",
        "package/subpackage/subpackage/__init__.py",
    }

    assert pf.get("./x:Import[@Project='$(PyMsbuildTargets){SEP}common.targets']") is not None
    assert pf.get("./x:Import[@Project='$(PyMsbuildTargets){SEP}pyd.targets']") is None


def test_package_project_reference(tmp_path):
    p = T.Package("package", T.PydFile("module", TargetExt=".TAG.pyd"))
    pf = ProjectFileChecker(G.generate(p, tmp_path, tmp_path))

    assert "package/module" == pf.get("./x:ItemGroup/x:Project[@Include='module.proj']/x:Name").text
    assert "package" == pf.get("./x:ItemGroup/x:Project[@Include='module.proj']/x:TargetDir").text
    assert "module.TAG" == pf.get("./x:ItemGroup/x:Project[@Include='module.proj']/x:TargetName").text
    assert ".pyd" == pf.get("./x:ItemGroup/x:Project[@Include='module.proj']/x:TargetExt").text


def test_pkginfo_gen_readback(tmp_path):
    with open(tmp_path / "txt.txt", "w", encoding="utf-8") as f:
        f.write("Test Data")
    d = {
        "Key": "Value",
        "Multikey": ["1", "2"],
        "File": T.File(tmp_path / "txt.txt"),
        "Description": "Multiple lines\nof text\nthat go at the end",
    }
    G.generate_distinfo(d, tmp_path, tmp_path)
    di = tmp_path / "PKG-INFO"
    assert di.is_file()
    d2 = G.readback_distinfo(di)
    d_check = {**d, "File": "Test Data"}
    assert d_check == d2

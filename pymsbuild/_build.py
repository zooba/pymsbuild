import os
from os.path import relpath
import pymsbuild
import shutil
import subprocess
import sys

from pathlib import PurePath, Path

import pymsbuild._types as _types
import pymsbuild.template as template


class BuildState:
    def __init__(
        self,
        distinfo,
        config_dir,
        build_dir,
        temp_dir,
        install_dir,
        msbuild_exe,
        globber,
    ):
        self.distinfo = distinfo
        self.config_dir = config_dir
        self.build_dir = build_dir
        self.temp_dir = temp_dir
        self.install_dir = install_dir
        self.msbuild_exe = msbuild_exe
        self.globber = globber
        self._built = {}

    def _generate_pyd(self, f, project, sources):
        print(template.PROLOGUE, file=f)
        print(template.VCPLATFORMS, file=f)
        print(template.get_PROPERTIES(self, project), file=f)
        print(template.get_VCPROPERTIES(self, project), file=f)

        print(template.ITEMS_START, file=f)
        for kind, src, dst in sources:
            print(template.get_ITEM(kind, src, dst), file=f)
        print(template.ITEMS_END, file=f)

        print(template.VCTARGETS, file=f)
        print(template.EPILOGUE, file=f)

    def _generate_lib(self, f, project, sources):
        print(template.PROLOGUE, file=f)
        print(template.get_PROPERTIES(self, project), file=f)

        print(template.ITEMS_START, file=f)
        for kind, src, dst in sources:
            print(template.get_ITEM(kind, src, dst), file=f)
        print(template.ITEMS_END, file=f)

        print(template.TARGETS, file=f)
        print(template.EPILOGUE, file=f)

    def generate(self, project):
        if project in self._built:
            return self._built[project]
        if "ProjectFile" in project.options:
            self._built[project] = out = project.options["ProjectFile"]
            return out

        print("Generating", project.target_name)
        out = (self.build_dir / project.target_name).with_suffix(".proj")
        out.parent.mkdir(parents=True, exist_ok=True)

        root = self.config_dir
        sources = [
            (kind, PurePath(source).relative_to(root), name)
            for kind, source, name in
            project._get_sources(root / project.root, self.globber)
        ]

        with out.open("w", encoding="utf-8") as f:
            if project._NATIVE_BUILD:
                self._generate_pyd(f, project, sources)
            else:
                self._generate_lib(f, project, sources)

        self._built[project] = out
        return out

    def generate_metadata(self, metadata_dir=None):
        metadata_dir = metadata_dir or self.build_dir
        outdir = metadata_dir / (self.distinfo["name"] + ".dist-info")
        outdir.mkdir(parents=True, exist_ok=True)

    def build(self, project, quiet=False):
        proj_file = self.generate(project)
        if quiet:
            run = subprocess.check_output
        else:
            run = subprocess.run
        print("Compiling", project.target_name, "with", self.msbuild_exe)
        try:
            run([
                self.msbuild_exe,
                proj_file,
                "/nologo",
                "/v:m",
                "/p:OutDirRoot={}".format(self.build_dir),
                "/p:IntDirRoot={}".format(self.temp_dir),
                "/p:FinalOutputDir={}".format(self.install_dir),
                "/p:SourceRoot={}".format(self.config_dir),
            ], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as ex:
            if quiet:
                print(ex.stdout.decode("mbcs", "replace"))
            sys.exit(1)
        else:
            pass

    def _layout_sdist(self, project):
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        proj = self.generate(project)
        yield proj, proj.relative_to(self.build_dir)
        with open(self.temp_dir / "_msbuild.py", "w", encoding="utf-8") as f:
            print("from pymsbuild import *", file=f)
            print("Package('{}', ProjectFile=r'{}').build(".format(
                project.target_name, proj.relative_to(self.build_dir)
            ), file=f)
        with open(self.temp_dir / "pyproject.toml", "w", encoding="utf-8") as f:
            print("[build-system]", file=f)
            print('requires = ["pymsbuild"]', file=f)
            print('build-backend = "pymsbuild"', file=f)
        yield self.temp_dir / "_msbuild.py", "_msbuild.py"
        yield self.temp_dir / "pyproject.toml", "pyproject.toml"
        q = list((project.root, m) for m in project._members)
        while q:
            root, m = q.pop(0)
            if isinstance(m, _types._Project):
                p = self.generate(m)
                yield p, p.relative_to(self.build_dir)
                q.extend((m.root, i) for i in m._members)
            elif isinstance(m, _types.File):
                yield self.config_dir / root / m.source, str(PurePath(root) / m.source)


    def layout_sdist(self, config_dir, dest_dir):
        config_dir = Path(config_dir)
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for src, dest_rel in self._layout_sdist(config_dir, dest_dir):
            dest = dest_dir / dest_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest, follow_symlinks=False)

    def build_sdist(self, project, copy_file):
        seen = set()
        for src, dest_rel in self._layout_sdist(project):
            if src not in seen:
                seen.add(src)
                copy_file(src, dest_rel)


def locate():
    exe = Path(os.getenv("MSBUILD", ""))
    if exe.is_file():
        return exe
    for part in os.getenv("PATH", "").split(os.path.pathsep):
        p = Path(part)
        if p.is_dir():
            exe = p / "msbuild.exe"
            if exe.is_file():
                return exe
    vswhere = Path(os.getenv("ProgramFiles(x86)"), "Microsoft Visual Studio", "Installer", "vswhere.exe")
    if vswhere.is_file():
        out = Path(subprocess.check_output([
            vswhere,
            "-nologo",
            "-property", "installationPath",
            "-latest",
            "-prerelease",
            "-products", "*",
            "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-utf8",
        ], encoding="utf-8", errors="strict").strip())
        if out.is_dir():
            exe = out / "MSBuild" / "Current" / "Bin" / "msbuild.exe"
            if exe.is_file():
                return exe

    raise RuntimeError("Unable to locate msbuild.exe. Please provide it as %MSBUILD%")

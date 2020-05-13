import os
from os.path import relpath
import pymsbuild
import shutil
import subprocess
import sys

from pathlib import Path

import pymsbuild._types as _types
import pymsbuild.template as template


class BuildState:
    def __init__(self, distinfo, project, sources, temp_dir):
        self.distinfo = distinfo
        self.project = project
        self.sources = list(sources or [])
        self.temp_dir = temp_dir

    def _generate_pyd(self, f, sources):
        print(template.PROLOGUE, file=f)
        print(template.VCPLATFORMS, file=f)
        print(template.get_PROPERTIES(self), file=f)
        print(template.get_VCPROPERTIES(self), file=f)

        print(template.ITEMS_START, file=f)
        for kind, src, dst in sources:
            print(template.get_ITEM(kind, src, dst), file=f)

        print(template.ITEMS_END, file=f)
        print(template.VCTARGETS, file=f)
        print(template.EPILOGUE, file=f)

    def _generate_lib(self, f, sources):
        print(template.PROLOGUE, file=f)
        print(template.get_PROPERTIES(self), file=f)

        print(template.ITEMS_START, file=f)
        for kind, src, dst in sources:
            print(template.get_ITEM(kind, src, dst), file=f)

        print(template.ITEMS_END, file=f)
        print(template.TARGETS, file=f)
        print(template.EPILOGUE, file=f)

    def generate(self, out_dir, sources):
        if self.project._explicit_project:
            return self.project._project_file

        out = (out_dir / self.project.target_name).with_suffix(".proj")
        out.parent.mkdir(parents=True, exist_ok=True)

        with out.open("w", encoding="utf-8") as f:
            if self.project._NATIVE_BUILD:
                self._generate_pyd(f, sources)
            else:
                self._generate_lib(f, sources)
        return out

    def generate_metadata(self, metadata_dir=None):
        metadata_dir = metadata_dir or self.build_dir
        outdir = metadata_dir / (self.project.target_name + ".dist-info")

    def build(self, msbuild_exe):
        proj_file = self.generate(self.temp_dir, self.sources)
        print(msbuild_exe, proj_file)
        subprocess.check_output([
            msbuild_exe,
            proj_file,
        ])

    def _layout_sdist(self, config_dir, temp_dir):
        yield config_dir / "_msbuild.py", "_msbuild.py"
        yield config_dir / "pyproject.toml", "pyproject.toml"
        sources = []
        for kind, src, name in self.sources:
            rel = Path(src).relative_to(config_dir)
            sources.append((kind, rel, name))
            yield Path(src), rel
        proj = self.generate(temp_dir, sources)
        yield Path(proj), proj.name

    def layout_sdist(self, config_dir, dest_dir):
        config_dir = Path(config_dir)
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for src, dest_rel in self._layout_sdist(config_dir, dest_dir):
            dest = dest_dir / dest_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest, follow_symlinks=False)

    def build_sdist(self, config_dir, temp_dir, sdist):
        config_dir = Path(config_dir)
        for src, dest_rel in self._layout_sdist(config_dir, temp_dir):
            sdist.add(src, dest_rel)


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

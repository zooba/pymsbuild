import os
import pymsbuild
import subprocess
import sys

from pathlib import Path

import pymsbuild._types as _types
import pymsbuild.template as template


class BuildState:
    def __init__(self, project, sources, build_dir, temp_dir, dist_dir):
        self.project = project
        self.sources = list(sources or [])
        self.build_dir = build_dir
        self.temp_dir = temp_dir
        self.dist_dir = dist_dir

    def _generate_pyd(self, f):
        print(template.PROLOGUE, file=f)
        print(template.VCPLATFORMS, file=f)
        print(template.get_PROPERTIES(self.project, self.build_dir, self.temp_dir), file=f)
        print(template.get_VCPROPERTIES(self.project), file=f)

        print(template.ITEMS_START, file=f)
        for kind, src, dst in self.sources:
            print(template.get_ITEM(kind, src, dst), file=f)

        print(template.ITEMS_END, file=f)
        print(template.VCTARGETS, file=f)
        print(template.EPILOGUE, file=f)

    def _generate_lib(self, f):
        print(template.PROLOGUE, file=f)
        print(template.get_PROPERTIES(self.project, self.build_dir, self.temp_dir), file=f)

        print(template.ITEMS_START, file=f)
        for kind, src, dst in self.sources:
            print(template.get_ITEM(kind, src, dst), file=f)

        print(template.ITEMS_END, file=f)
        print(template.TARGETS, file=f)
        print(template.EPILOGUE, file=f)

    def generate_project(self):
        if self.project._explicit_project:
            return self.project._project_file

        out = (self.temp_dir / self.project.target_name).with_suffix(".proj")
        out.parent.mkdir(parents=True, exist_ok=True)

        with out.open("w", encoding="utf-8") as f:
            if self.project._NATIVE_BUILD:
                self._generate_pyd(f)
            else:
                self._generate_lib(f)
        return out

    def generate_metadata(self, metadata_dir=None):
        metadata_dir = metadata_dir or self.build_dir
        outdir = metadata_dir / (self.project.target_name + ".dist-info")

    def build(self, msbuild_exe):
        proj_file = self.generate_project()
        #print(msbuild_exe, proj_file)
        subprocess.check_output([
            msbuild_exe,
            proj_file,
        ])


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

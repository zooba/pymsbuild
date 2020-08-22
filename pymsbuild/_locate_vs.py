import os
import subprocess

from pathlib import Path


def _locate_msbuild():
    exe = os.getenv("MSBUILD", "")
    if exe:
        if Path(exe).is_file():
            return f'"{exe}"'
        return exe
    
    for part in os.getenv("PATH", "").split(os.path.pathsep):
        p = Path(part)
        if p.is_dir():
            exe = p / "msbuild.exe"
            if exe.is_file():
                return f'"{exe}"'

    vswhere = Path(os.getenv("ProgramFiles(x86)"), "Microsoft Visual Studio", "Installer", "vswhere.exe")
    if vswhere.is_file():
        out = Path(subprocess.check_output([
            str(vswhere),
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
                return f'"{exe}"'

    try:
        out = subprocess.check_output(
            "dotnet build -version -nologo",
            encoding="ascii",
            errors="replace",
        )
        version = int(out.partition(".")[0])
        if version >= 15:
            return "dotnet build"
    except Exception:
        pass

    # TODO: Also look for .NET Core SDK installation

    raise RuntimeError("Unable to locate msbuild.exe. Please provide it as %MSBUILD%")

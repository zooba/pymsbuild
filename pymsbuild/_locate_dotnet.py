import os
import shlex
import shutil
import subprocess

from pathlib import Path

def _check_build(dotnet):
    try:
        out = subprocess.check_output(
            [dotnet, "build", "-version", "-nologo"],
            encoding="ascii",
            errors="replace",
        )
        version = int(out.partition(".")[0])
        if version >= 15:
            return [dotnet, "build"]
    except Exception:
        raise RuntimeError("Unable to locate 'dotnet build'. Please provide it as %MSBUILD%")

    raise RuntimeError("Unable to locate 'dotnet build'. Please provide it as %MSBUILD%")


def locate_msbuild():
    exe = os.getenv("MSBUILD", "")
    if exe:
        return shlex.split(exe)

    try:
        from dotnetcore2.runtime import ensure_dependencies, get_runtime_path
    except ImportError:
        pass
    else:
        ensure_dependencies()
        try:
            return _check_build(get_runtime_path())
        except RuntimeError:
            pass

    return _check_build("dotnet")

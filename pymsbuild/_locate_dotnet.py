import os
import shutil
import subprocess

from pathlib import Path

def _locate_msbuild():
    exe = os.getenv("MSBUILD", "")
    if exe:
        if Path(exe).is_file():
            return f'"{exe}"'
        return exe
    
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
        raise RuntimeError("Unable to locate 'dotnet build'. Please provide it as %MSBUILD%")

    raise RuntimeError("Unable to locate 'dotnet build'. Please provide it as %MSBUILD%")

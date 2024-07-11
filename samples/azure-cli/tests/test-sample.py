import os
import pathlib
import subprocess

AZ_EXE = "az.exe" if os.name == "nt" else "az"

AZ = pathlib.Path(os.getenv("BUILD_PREFIX")) / "azure-cli" / AZ_EXE

assert AZ.is_file()

subprocess.check_call([AZ, "--help", "--debug"])

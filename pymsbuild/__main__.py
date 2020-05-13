import pymsbuild
import sys

from pathlib import Path

if "init" in sys.argv[1:]:
    print("TODO: Generate workflow")
    sys.exit(2)

from pymsbuild import read_config, build_in_place
config = read_config(Path.cwd())
build_in_place(config.parent, config.parent / "build")


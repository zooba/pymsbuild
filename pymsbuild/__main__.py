import pymsbuild
import sys

from pathlib import Path

if "init" in sys.argv[1:]:
    print("TODO: Generate workflow")
    sys.exit(2)

from pymsbuild import read_config, generate
config = read_config(Path.cwd())

if "generate" in sys.argv[1:]:
    generate(config)

"""
if "sdist" in sys.argv[1:]:
    build_sdist(config.parent / "dist")
elif "prepare" in sys.argv[1:]:
    prepare_metadata_for_build_wheel(config.parent)
elif "clean" in sys.argv[1:]:
    build_in_place(target="Clean")
else:
    build_in_place(target="Install")

"""

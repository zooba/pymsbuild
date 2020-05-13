import pymsbuild
import sys

from pathlib import Path

if "init" in sys.argv[1:]:
    print("TODO: Generate workflow")
    sys.exit(2)

try:
    sdist_dir = Path(sys.argv[sys.argv.index("sdist") + 1])
except (IndexError, ValueError):
    sdist_dir = None

try:
    wheel_dir = Path(sys.argv[sys.argv.index("wheel") + 1])
except (IndexError, ValueError):
    wheel_dir = None

from pymsbuild import read_config, build_in_place, build_sdist, build_wheel
config = read_config(Path.cwd())

if sdist_dir:
    build_sdist(config.parent / "sdist")
else:
    build_in_place(config.parent, config.parent / "build")


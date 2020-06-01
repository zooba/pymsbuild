import argparse
import pymsbuild
import sys

from pathlib import PurePath, Path

def parse_args():
    parser = argparse.ArgumentParser("pymsbuild")
    parser.add_argument("--force", "-f", action="store_true", help="Force a full rebuild")
    parser.add_argument("--verbose", "-v", action="store_true", help="Additional output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Less output")
    parser.add_argument("--source-dir", "-s", type=PurePath, default=None, help="Specify the source directory")
    parser.add_argument("--dist-dir", "-d", type=PurePath, default=None, help="Set the temporary directory")
    parser.add_argument("--temp-dir", "-t", type=PurePath, default=None, help="Set the build artifacts directory")
    parser.add_argument("--config", "-c", type=PurePath, default=None, help="Override the path to _msbuild.py")

    subparser = parser.add_subparsers()
    p = subparser.add_parser("init", help="Initialise a new _msbuild.py file")
    p.set_defaults(cmd="init")
    p = subparser.add_parser("generate", help="Generate the build files without building")
    p.set_defaults(cmd="generate")
    p = subparser.add_parser("sdist", help="Build an sdist")
    p.set_defaults(cmd="build_sdist")
    p = subparser.add_parser("wheel", help="Build a wheel")
    p.set_defaults(cmd="build_wheel")
    p = subparser.add_parser("distinfo", help="Build just the wheel metadata")
    p.set_defaults(cmd="prepare_wheel_distinfo")
    p = subparser.add_parser("clean", help="Clean any builds")
    p.set_defaults(cmd="clean")

    return parser.parse_args()

ns = parse_args()
if not hasattr(ns, "cmd"):
    ns.cmd = "build_in_place"

if ns.cmd == "init":
    print("TODO: Generate workflow")
    sys.exit(2)

bs = pymsbuild.BuildState()
bs.source_dir = Path.cwd() / (ns.source_dir or "")
bs.output_dir = bs.source_dir / (ns.dist_dir or "dist")
bs.config_file = ns.config
root_dir = bs.source_dir / (ns.temp_dir or "build")
bs.build_dir = root_dir / "layout"
bs.temp_dir = root_dir / "temp"
bs.verbose = ns.verbose
bs.quiet = ns.quiet
bs.force = ns.force

cmd = getattr(bs, ns.cmd)
cmd()

import argparse
import pymsbuild
import sys

from os import getenv
from pathlib import PurePath, Path
from pymsbuild._build import BuildState


def _env(var, default=None):
    v = getenv(var)
    if not v:
        return default
    return v


def _envp(var, default=None):
    v = getenv(var)
    if not v:
        return default
    return PurePath(v)


def _envbool(var, default=None, is_true=True, is_false=False):
    v = getenv(var)
    if not v:
        return default
    if v.lower() in {"no", "0", "false"}:
        return is_false
    return is_true


def parse_args():
    parser = argparse.ArgumentParser("pymsbuild",)
    parser.add_argument(
        "--force", "-f", action="store_true", help="Force a full rebuild"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Additional output"
    )
    parser.add_argument("--quiet", "-q", action="store_true", help="Less output")
    parser.add_argument(
        "--debug", "-g", action="store_true", help="Build in debugging configuration"
    )
    parser.add_argument(
        "--source-dir",
        "-s",
        type=PurePath,
        default=_envp("PYMSBUILD_SOURCE_DIR"),
        help="Specify the source directory",
    )
    parser.add_argument(
        "--dist-dir",
        "-d",
        type=PurePath,
        default=_envp("PYMSBUILD_DIST_DIR"),
        help="Set the packaged outputs directory",
    )
    parser.add_argument(
        "--temp-dir",
        "-t",
        type=PurePath,
        default=_envp("PYMSBUILD_TEMP_DIR"),
        help="Set the temporary working directory",
    )
    parser.add_argument(
        "--layout-dir",
        type=PurePath,
        default=_envp("PYMSBUILD_LAYOUT_DIR"),
        help="Set the layout directory and enable two-step build",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=PurePath,
        default=_envp("PYMSBUILD_CONFIG"),
        help="Override the path to _msbuild.py",
    )
    parser.add_argument(
        "--add",
        type=str,
        nargs="*",
        help="Specify additional file(s) to package when using the 'pack' command."
    )
    parser.add_argument(
        "command",
        type=str,
        nargs="*",
        help="""one or more of 'init', 'generate', 'sdist', 'wheel', 'pack', 'distinfo', 'clean'

init: Initialise a new _msbuild.py file.
generate: Generate the build files without building.
sdist: Build an sdist.
wheel: Build a wheel.
pack: Perform the second step of a two-step build.
distinfo: Build just the wheel metadata.
clean: Clean any builds.
""",
    )

    ns = parser.parse_args()
    if _envbool("PYMSBUILD_FORCE"):
        ns.force = True
    if _envbool("PYMSBUILD_VERBOSE"):
        ns.verbose = True
    if _envbool("PYMSBUILD_QUIET"):
        ns.quiet = True
    if _envbool("PYMSBUILD_DEBUG"):
        ns.debug = True

    return ns


ns = parse_args()
if not getattr(ns, "command", None):
    ns.command = ["build_in_place"]

if "init" in ns.command:
    from . import _init
    _init.run(Path.cwd(), ns.config)
    sys.exit(0)

bs = BuildState()
bs.source_dir = Path.cwd() / (ns.source_dir or "")
bs.output_dir = bs.source_dir / (ns.dist_dir or "dist")
bs.config_file = ns.config
root_dir = bs.source_dir / (ns.temp_dir or "build")
bs.build_dir = root_dir / "layout"
bs.temp_dir = root_dir / "temp"
bs.layout_dir = ns.layout_dir
bs.layout_extra_files = ns.add
bs.verbose = ns.verbose
bs.quiet = ns.quiet
bs.force = ns.force
if ns.debug:
    bs.configuration = "Debug"

for cmd in ns.command:
    cmd = {
        "sdist": "build_sdist",
        "wheel": "build_wheel",
        "distinfo": "prepare_wheel_distinfo",
    }.get(cmd, cmd)
    f = getattr(bs, cmd)
    f()

import argparse
import pymsbuild
import sys

from os import getenv
from pathlib import PurePath, Path
from pymsbuild._build import BuildState
from pymsbuild._init import run as run_init


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


def parse_args(commands):
    parser = argparse.ArgumentParser(
        "pymsbuild",
        formatter_class=argparse.RawTextHelpFormatter,
    )
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
    cmd_help_1 = ", ".join(f"'{k}'" for k, (f, doc) in commands.items() if doc)
    cmd_help_2 = "\n".join(f"{k}: {doc}" for k, (f, doc) in commands.items() if doc)
    parser.add_argument(
        "command",
        type=str,
        default="build_in_place",
        nargs="?",
        help=f"one of {cmd_help_1}.\n\n{cmd_help_2}",
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


COMMANDS = {
    "init": (run_init, "Initialise a new _msbuild.py file."),
    "generate": (BuildState.generate, "Generate the build files without building."),
    "sdist": (BuildState.build_sdist, "Build an sdist."),
    "wheel": (BuildState.build_wheel, "Build a wheel."),
    "pack": (BuildState.pack, "Perform the second step of a two-step build."),
    "distinfo": (BuildState.prepare_wheel_distinfo, "Build just the wheel metadata"),
    "clean": (BuildState.clean, "Clean any builds."),
    "build_in_place": (BuildState.build_in_place, None),
}


ns = parse_args(COMMANDS)


if ns.verbose:
    print("pymsbuild", pymsbuild.__version__, "running on", sys.version.partition("\n")[0])


bs = BuildState()
bs.source_dir = Path.cwd() / (ns.source_dir or "")
bs.output_dir = bs.source_dir / (ns.dist_dir or "dist")
bs.config_file = ns.config
root_dir = bs.source_dir / (ns.temp_dir or "build")
bs.build_dir = root_dir / "bin"
bs.temp_dir = root_dir / "temp"
bs.layout_dir = ns.layout_dir
bs.layout_extra_files = ns.add
bs.verbose = ns.verbose
bs.quiet = ns.quiet
bs.force = ns.force
if ns.debug:
    bs.configuration = "Debug"


if _envbool("PYMSBUILD_SHOW_TRACEBACKS"):
    f, doc = COMMANDS[ns.command]
    f(bs)
    sys.exit(0)


try:
    f, doc = COMMANDS[ns.command]
except KeyError:
    print(
        "ERROR: Unrecognised command. See 'python -m pymsbuild --help' " +
        "for the list of valid commands.",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    f(bs)
except Exception as ex:
    print("ERROR", ex, file=sys.stderr)
    if getattr(ex, "winerror", 0):
        sys.exit(ex.winerror)
    if getattr(ex, "errno", 0):
        sys.exit(ex.errno)
    sys.exit(1)

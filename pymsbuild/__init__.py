"""The pymsbuild build backend.
"""

__version__ = "%VERSION%"
try:
    NEXT_INCOMPATIBLE_VERSION = "{}.0".format(int(__version__.partition(".")[0]) + 1)
    PYMSBUILD_REQUIRES_SPEC = f"pymsbuild>={__version__},<{NEXT_INCOMPATIBLE_VERSION}"
except ValueError:
    PYMSBUILD_REQUIRES_SPEC = "pymsbuild"


from pymsbuild._build import BuildState as _BuildState
from pymsbuild._types import *


def get_current_build_state():
    return _BuildState.current


def build_sdist(sdist_directory, config_settings=None):
    bs = _BuildState(sdist_directory)
    return bs.build_sdist()


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    bs = _BuildState(wheel_directory)
    return bs.build_wheel()


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    bs = _BuildState(metadata_directory)
    bs.metadata_dir = metadata_directory
    return bs.prepare_wheel_distinfo()


def get_requires_for_build_sdist(config_settings=None):
    bs = _BuildState()
    return bs.get_requires_for_build_sdist()


def get_requires_for_build_wheel(config_settings=None):
    bs = _BuildState()
    return bs.get_requires_for_build_wheel()


def _get_extension_commands(log=print):
    try:
        import entrypoints
    except ImportError:
        # No way to resolve entrypoints, which must mean no extensions exist
        # If you're an extension, declare this dependency yourself.
        return

    def _get_extension_doc(k, f):
        try:
            return f.__doc__.partition("\n")[0].strip()
        except (AttributeError, ValueError):
            return f"Invokes {k}"

    for k, v in entrypoints.get_group_named("pymsbuild.command"):
        try:
            cmd = v.load()
        except Exception as ex:
            log("Failed to load extension command", v.name)
            log(ex)
        else:
            yield k, (cmd, _get_extension_doc(k, cmd))

    # Can also test a single command by setting this environment variable.
    # Syntax is name=module:func
    import os
    spec = os.getenv("PYMSBUILD_EXTENSION_COMMAND")
    if spec:
        try:
            k, _, v = spec.partition("=")
            cmd = entrypoints.EntryPoint.from_string(v, k).load()
            yield k, (cmd, _get_extension_doc(k, cmd))
        except Exception as ex:
            log("Failed to load extension command from environment:", spec)
            log(ex)

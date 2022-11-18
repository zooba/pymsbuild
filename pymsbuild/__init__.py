"""The pymsbuild build backend.
"""

__version__ = "0.0.1"

from pymsbuild._build import BuildState as _BuildState
from pymsbuild._types import *


def build_sdist(sdist_directory, config_settings=None):
    bs = _BuildState(sdist_directory)
    return bs.build_sdist()


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    bs = _BuildState(wheel_directory)
    return bs.build_wheel()


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    bs = _BuildState(metadata_directory)
    return bs.prepare_wheel_distinfo(bs.output_dir)


def get_requires_for_build_sdist(config_settings=None):
    bs = _BuildState()
    return bs.get_requires_for_build_sdist()


def get_requires_for_build_wheel(config_settings=None):
    bs = _BuildState()
    return bs.get_requires_for_build_wheel()

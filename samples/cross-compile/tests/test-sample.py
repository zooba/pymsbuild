import sys

from cross_compile_sample._native import properties

version, python_tag, abi_tag, platform_tag, cross_compile = properties()

assert version == f"{sys.version_info.major}.{sys.version_info.minor}"
assert python_tag
assert abi_tag
assert platform_tag
assert cross_compile == "False"

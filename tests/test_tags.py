import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pymsbuild
import pymsbuild._tags as T

def test_remap_platform():
    assert T.remap_platform_to_msbuild("win32") == "Win32"
    assert T.remap_platform_to_msbuild("win_amd64") == "x64"
    assert T.remap_platform_to_msbuild("linux_x86_64") == "POSIX_x64"
    assert T.remap_platform_to_msbuild("manylinux1_x86_64") == "POSIX_x64"

def test_remap_ext_to_abi():
    assert T.remap_ext_to_abi("cp37-win_amd64") == "cp37m-win_amd64"
    assert T.remap_ext_to_abi("cp38-win_amd64") == "cp38-win_amd64"
    assert T.remap_ext_to_abi("cp311-win_amd64") == "cp311-win_amd64"

    assert T.remap_ext_to_abi("cpython-37m-x86_64-linux-gnu") == "cp37m-linux_x86_64"
    assert T.remap_ext_to_abi("cpython-38-x86_64-linux-gnu") == "cp38-linux_x86_64"
    assert T.remap_ext_to_abi("cpython-311-x86_64-linux-gnu") == "cp311-linux_x86_64"

def test_remap_abi_to_ext():
    assert T.remap_abi_to_ext("cp37m-win_amd64") == "cp37-win_amd64"
    assert T.remap_abi_to_ext("cp38-win_amd64") == "cp38-win_amd64"
    assert T.remap_abi_to_ext("cp311-win_amd64") == "cp311-win_amd64"

    assert T.remap_abi_to_ext("cp37m-linux_x86_64") == "cpython-37m-x86_64-linux-gnu"
    assert T.remap_abi_to_ext("cp38-linux_x86_64") == "cpython-38-x86_64-linux-gnu"
    assert T.remap_abi_to_ext("cp311-linux_x86_64") == "cpython-311-x86_64-linux-gnu"

def tags_as_dict(t):
    return {k: getattr(t, k) for k in ("abi_tag", "platform_tag", "ext_suffix", "wheel_tag")}

def test_choose_best_tags_from_abi():
    r = T.choose_best_tags("py399-cp399-plat", ".cp399-plat.ext", abi_tag="cp311-win_amd64")
    assert tags_as_dict(r) == dict(
        abi_tag = "cp311-win_amd64",
        platform_tag = "win_amd64",
        ext_suffix = ".cp311-win_amd64.ext",
        wheel_tag = "py399-cp311-win_amd64",
    )

def test_choose_best_tags_from_ext():
    r = T.choose_best_tags("py399-cp399-plat", ".cp399-plat.ext", ext_suffix=".cp311-win_amd64.pyd")
    assert tags_as_dict(r) == dict(
        abi_tag = "cp311-win_amd64",
        platform_tag = "win_amd64",
        ext_suffix = ".cp311-win_amd64.pyd",
        wheel_tag = "py399-cp311-win_amd64",
    )

def test_choose_best_tags_from_platform():
    r = T.choose_best_tags("py399-cp399-plat", ".cp399-plat.ext", platform_tag="win_amd64")
    assert tags_as_dict(r) == dict(
        abi_tag = "cp399-win_amd64",
        platform_tag = "win_amd64",
        ext_suffix = ".cp399-win_amd64.ext",
        wheel_tag = "py399-cp399-win_amd64",
    )

def test_choose_best_tags_from_wheel():
    r = T.choose_best_tags("py399-cp399-plat", ".cp399-plat.ext", wheel_tag="py311-cp311-win_amd64")
    assert tags_as_dict(r) == dict(
        abi_tag = "cp311-win_amd64",
        platform_tag = "win_amd64",
        ext_suffix = ".cp311-win_amd64.ext",
        wheel_tag = "py311-cp311-win_amd64",
    )

def test_choose_best_tags_from_wheel_no_interpreter():
    r = T.choose_best_tags("py399-cp399-plat", ".cp399-plat.ext", wheel_tag="*-cp311-win_amd64")
    assert tags_as_dict(r) == dict(
        abi_tag = "cp311-win_amd64",
        platform_tag = "win_amd64",
        ext_suffix = ".cp311-win_amd64.ext",
        wheel_tag = "py399-cp311-win_amd64",
    )

def test_choose_best_tags_from_wheel_no_platform():
    r = T.choose_best_tags("py399-cp399-plat", ".cp399-plat.ext", wheel_tag="py311-cp311-*")
    assert tags_as_dict(r) == dict(
        abi_tag = "cp311-plat",
        platform_tag = "plat",
        ext_suffix = ".cp311-plat.ext",
        wheel_tag = "py311-cp311-plat",
    )

def test_choose_best_tags_from_wheel_no_abi():
    r = T.choose_best_tags("py399-cp399-plat", ".cp399-plat.ext", wheel_tag="py311-*-win_amd64")
    assert tags_as_dict(r) == dict(
        abi_tag = "cp399-win_amd64",
        platform_tag = "win_amd64",
        ext_suffix = ".cp399-win_amd64.ext",
        wheel_tag = "py311-cp399-win_amd64",
    )

import re
import sysconfig
import types

from packaging.tags import Tag, parse_tag, sys_tags


_TAG_PLATFORM_MAP = {
    "win32": "Win32",
    "win_amd64": "x64",
    "win_arm": "ARM",
    "win_arm64": "ARM64",
    "linux_x86_64": "POSIX_x64",
    "linux_aarch64": "POSIX_ARM64",
    "macosx_10_15_x86_64": "POSIX_x64",
    "any": None,
}


def remap_platform_to_msbuild(platform_tag):
    try:
        return _TAG_PLATFORM_MAP[platform_tag]
    except LookupError:
        if re.match(r"manylinux.+?_x86_64", platform_tag):
            return "POSIX_x64"
        raise


def remap_ext_to_abi(ext_tag):
    m = re.match(r"(cp\d+)-(win.+)", ext_tag)
    if m:
        # Matches Windows-style tag
        abi = "m" if m.group(1) in {"cp37"} else ""
        return "{0}{abi}-{1}".format(*m.groups(), abi=abi)
    m = re.match(r"cpython-(\d+m?)-(.+)-linux-gnu", ext_tag)
    if m:
        # Matches Linux/GNU style tag
        return "cp{0}-linux_{1}".format(*m.groups())
    return ext_tag


def remap_abi_to_ext(abi_tag):
    m = re.match(r"(cp\d+)m?-(win.+)", abi_tag)
    if m:
        # Matches Windows-style tag
        return "{0}-{1}".format(*m.groups())
    m = re.match(r"cp(\d+m?)-linux_(.+)", abi_tag)
    if m:
        # Matches Linux/GNU style tag
        return "cpython-{0}-{1}-linux-gnu".format(*m.groups())
    m = re.match(r"cp(\d+m?)-manylinux.+?_(.+)", abi_tag)
    if m:
        # Matches manylinux style tag
        return "cpython-{0}-{1}-linux-gnu".format(*m.groups())
    return abi_tag


def choose_best_tags(
    sys_wheel_tag=None,
    sys_ext_suffix=None,
    wheel_tag=None,
    abi_tag=None,
    platform_tag=None,
    ext_suffix=None
):
    if not sys_wheel_tag:
        sys_wheel_tag = next(iter(sys_tags()), None) or "py3-none-any"

    if not sys_ext_suffix:
        sys_ext_suffix = sysconfig.get_config_var("EXT_SUFFIX")
        if not sys_ext_suffix:
            import importlib.machinery
            sys_ext_suffix = importlib.machinery.EXTENSION_SUFFIXES[0]

    if sys_wheel_tag and not isinstance(sys_wheel_tag, Tag):
        sys_wheel_tag = next(iter(parse_tag(sys_wheel_tag)), None)

    if wheel_tag and not isinstance(wheel_tag, Tag):
        # Ensure we can correctly parse the tag, but then just split
        # We don't want to expand out compressed fields
        if next(iter(parse_tag(wheel_tag)), None):
            wheel_tag = Tag(*wheel_tag.split('-', 3))

    # Extract the ABI portion from an explicit ABI tag or wheel tag
    abi_only = None
    if abi_tag:
        abi_only = abi_tag.partition('-')[0]
    elif wheel_tag and wheel_tag.abi != "*" and "." not in wheel_tag.abi:
        abi_only = wheel_tag.abi

    # Overwrite the ABI tag and platform tag from an explicit wheel tag
    if wheel_tag:
        if not abi_tag and "*" not in (wheel_tag.abi, wheel_tag.platform):
            abi_tag = f"{wheel_tag.abi}-{wheel_tag.platform}"
            if "." in abi_tag:
                abi_tag = None
        if not platform_tag and wheel_tag.platform != "*" and "." not in wheel_tag.platform:
            platform_tag = wheel_tag.platform

    # Infer the ABI tag from explicit or default ext_suffix, and update the ABI
    # portion accordingly
    if not abi_tag:
        if ext_suffix:
            abi_tag = remap_ext_to_abi(ext_suffix.rpartition('.')[0].strip('.'))
        else:
            abi_tag = remap_ext_to_abi(sys_ext_suffix.rpartition('.')[0].strip('.'))
            if abi_tag and platform_tag:
                abi_tag = "{}-{}".format(abi_tag.partition('-')[0], platform_tag)
        if abi_tag:
            if abi_only:
                abi_tag = "{}-{}".format(abi_only, abi_tag.partition('-')[2])
            else:
                abi_only = abi_tag.partition('-')[0]

    # Infer the platform from the ABI tag or default wheel tag
    if not platform_tag:
        if abi_tag:
            platform_tag = abi_tag.partition('-')[2]
        else:
            platform_tag = sys_wheel_tag.platform

    # Infer the ext_suffix from the ABI tag or default ext_suffix
    if not ext_suffix:
        if abi_tag:
            ext_suffix = '.{}.{}'.format(
                remap_abi_to_ext(abi_tag),
                sys_ext_suffix.rpartition('.')[2]
            )
        else:
            ext_suffix = sys_ext_suffix

    # Infer the ABI portion from the default wheel tag
    if not abi_only:
        abi_only = sys_wheel_tag.abi

    # Final chance for ABI
    if not abi_tag:
        abi_tag = f"{abi_only}-{platform_tag}"

    if not abi_tag.startswith(abi_only):
        raise ValueError(f"Expected '{abi_tag}' to start with '{abi_only}'")

    # Infer any missing parts of the wheel tag
    if not wheel_tag:
        wheel_tag = Tag(sys_wheel_tag.interpreter, abi_only, platform_tag)
    if wheel_tag.interpreter == '*':
        wheel_tag = Tag(sys_wheel_tag.interpreter, wheel_tag.abi, wheel_tag.platform)
    if wheel_tag.abi == '*':
        wheel_tag = Tag(wheel_tag.interpreter, abi_only, wheel_tag.platform)
    if wheel_tag.platform == '*':
        wheel_tag = Tag(wheel_tag.interpreter, wheel_tag.abi, platform_tag)

    return types.SimpleNamespace(
        wheel_tag=str(wheel_tag),
        abi_tag=abi_tag,
        platform_tag=platform_tag,
        ext_suffix=ext_suffix,
    )

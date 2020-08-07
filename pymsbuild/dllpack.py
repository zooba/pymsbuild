import sys

from pathlib import Path
from pymsbuild._types import *

class DllPackage(PydFile):
    r"""Represents a DLL-packed package.
"""
    options = {
        **PydFile.options,
    }

    def __init__(self, name, *members, project_file=None, **kwargs):
        super().__init__(
            name,
            Property("BeforeBuildGenerateSourcesTargets", "GenerateDllPack;$(BeforeBuildGenerateSourcesTargets)"),
            *members,
            LiteralXML('<Import Project="$(PyMsbuildTargets)\\dllpack.targets" />'),
            project_file=project_file,
            **kwargs
        )


FIRST_PYC_RES_ID = 1000
FIRST_NAME_RES_ID = 10000
FIRST_ORIGIN_RES_ID = 20000

def _compile_one(origin, source, dest):
    import py_compile
    py_compile.compile(
        str(source),
        dest,
        origin,
        doraise=True,
        optimize=0,
        invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
    )


def _write_rc_string(id, s, file):
    print(id, '"', end="", file=file)
    while len(s) > 4000:
        print(s[:4000], "\\", sep="", file=file)
        s = s[4000:]
    print(s, '"', sep="", file=file)


def _generate_files(target, sources):
    with open("dllpack.h", "w", encoding="ascii", errors="backslashescape") as h_file:
        print('#define _MODULE_NAME "{}"'.format(target), file=h_file)
        print('#define _INIT_FUNC_NAME PyInit_{}'.format(target), file=h_file)
        print("#define _FIRST_PYC_RES_ID", FIRST_PYC_RES_ID, file=h_file)
        print("#define _FIRST_NAME_RES_ID", FIRST_NAME_RES_ID, file=h_file)
        print("#define _FIRST_ORIGIN_RES_ID", FIRST_ORIGIN_RES_ID, file=h_file)
        print("#define _MODULE_COUNT", len(sources), file=h_file)
        print("#define _PYCFILE 257", file=h_file)

    for i, (name, src) in enumerate(sources, start=FIRST_PYC_RES_ID):
        _compile_one(name, src, Path.cwd() / "pyc{}.bin".format(i))

    with open("dllpack.rc", "w", encoding="ascii", errors="backslashescape") as rc_file:
        print("// Generated", name, "from", src, file=rc_file)
        print("#define PYCFILE 257", file=rc_file)
        for i, (name, src) in enumerate(sources, start=FIRST_PYC_RES_ID):
            print("{0} PYCFILE pyc{0}.bin".format(i), file=rc_file)
        print("STRINGTABLE", file=rc_file)
        print("BEGIN", file=rc_file)
        for i, (name, src) in enumerate(sources):
            n = name.partition(".")[0].replace("/", ".")
            _write_rc_string(i + FIRST_NAME_RES_ID, n, rc_file)
            _write_rc_string(i + FIRST_ORIGIN_RES_ID, name, rc_file)
        print("END", file=rc_file)


if __name__ == "__main__":
    import sys
    TARGET = sys.argv[1]
    FILES = []
    with open(sys.argv[2], "r", encoding="utf-8-sig") as f:
        for s in map(str.strip, f):
            name, _, filename = s.partition(":")
            FILES.append((name, Path(filename)))
    _generate_files(TARGET, FILES)
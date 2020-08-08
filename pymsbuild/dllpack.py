import sys

from pathlib import Path, PureWindowsPath
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


class _FileInfo:
    _resid_counter = iter(range(1001, 9999))

    CODE_EXTENSIONS = frozenset(s.casefold() for s in [".py", ".pyc", ".pyw"])
    PYC_EXTENSIONS = frozenset(s.casefold() for s in [".pyc"])

    def __init__(self):
        self.name = None
        self.origin = None
        self.sourcefile = None
        self.resid = next(self._resid_counter)
        self.postexec_resid = 0
        self.is_package = False
        self.is_code = False
        self.is_pyc = False

    def compile_pyc(self, optimize=0):
        if self.is_pyc:
            return self.sourcefile
        if not self.is_code:
            return None
        import py_compile
        return Path(py_compile.compile(
            str(self.sourcefile),
            "pyc{}.bin".format(self.resid),
            self.origin,
            doraise=True,
            optimize=optimize,
            invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
        ))

    @classmethod
    def parse(cls, line):
        name, _, filename = line.partition(":")
        if not name or not filename:
            return None
        f = cls()
        f.sourcefile = Path(filename)
        p = PureWindowsPath(name)
        f.origin = str(p)
        f.is_package = p.stem.casefold() == "__init__".casefold()
        f.is_code = (p.suffix.casefold() in cls.CODE_EXTENSIONS)
        f.is_pyc = (p.suffix.casefold() in cls.PYC_EXTENSIONS)
        if f.is_code:
            name_parts = list(p.with_suffix("").parts)
            if f.is_package:
                name_parts.pop()
        else:
            name_parts = p.parts
        f.name = ".".join(name_parts)
        return f

    @classmethod
    def get_builtin(cls, sourcefile):
        f = cls()
        f.sourcefile = sourcefile
        f.name = "${}".format(sourcefile.stem)
        f.is_code = True
        return f


def _write_rc_string(id, s, file):
    print(id, '"', end="", file=file)
    while len(s) > 4000:
        print(s[:4000], "\\", sep="", file=file)
        s = s[4000:]
    print(s, '"', sep="", file=file)


def _path_str(s):
    return '"' + (
        str(s).replace("\\", "\\\\").replace('"', '\\"')
    ) + '"'

def _generate_files(module, sources, targets):
    f_main = _FileInfo.get_builtin(targets / "dllpack_main.py")

    with open("dllpack.rc", "w", encoding="ascii", errors="backslashescape") as rc_file:
        print("#define PYCFILE 257", file=rc_file)
        print("#define DATAFILE 258", file=rc_file)
        for f in [*sources, f_main]:
            if not f:
                continue
            pyc = f.compile_pyc()
            if pyc:
                print(f.resid, "PYCFILE", _path_str(pyc), file=rc_file)
            else:
                print(f.resid, "DATAFILE", _path_str(f.sourcefile), file=rc_file)

    with open("dllpack.h", "w", encoding="ascii", errors="backslashescape") as h_file:
        print('#define _MODULE_NAME "{}"'.format(module), file=h_file)
        print('#define _IMPORTERS_MODULE_NAME "${}_importers"'.format(module), file=h_file)
        print('#define _INIT_FUNC_NAME PyInit_{}'.format(module), file=h_file)
        print("#define _PYCFILE 257", file=h_file)
        print("#define _DATAFILE 258", file=h_file)
        print("#define _PYC_HEADER_LEN 16", file=h_file)
        print("struct ENTRY {const char *name; const char *origin; int id; int preexec_id; int package;};", file=h_file)
        print("struct ENTRY IMPORT_TABLE[] = {", file=h_file)
        for f in sources:
            if not f or not f.is_code:
                continue
            preexec_resid = 0
            if f.name == module:
                preexec_resid = f_main.resid
            print("    {", file=h_file)
            print('        {},'.format(_path_str(f.name)), file=h_file)
            print('        {},'.format(_path_str(f.origin)), file=h_file)
            print("        {}, {},".format(f.resid, preexec_resid), file=h_file)
            print("        {}".format(1 if f.is_package else 0), file=h_file)
            print("    },", file=h_file)
        print("    {NULL, NULL, 0, 0, 0}", file=h_file)
        print("};", file=h_file)
        print("struct ENTRY DATA_TABLE[] = {", file=h_file)
        for f in sources:
            if not f or f.is_code:
                continue
            print("    {", file=h_file)
            print('        {},'.format(_path_str(f.name)), file=h_file)
            print('        {},'.format(_path_str(f.origin)), file=h_file)
            print("        {}, 0, 0".format(f.resid), file=h_file)
            print("    },", file=h_file)
        print("    {NULL, NULL, 0, 0}", file=h_file)
        print("};", file=h_file)


if __name__ == "__main__":
    import sys
    MODULE = sys.argv[1]
    FILES = []
    with open(sys.argv[2], "r", encoding="utf-8-sig") as f:
        FILES = [_FileInfo.parse(s.strip()) for s in f]
    TARGETS = Path(sys.argv[3])
    _generate_files(MODULE, FILES, TARGETS)

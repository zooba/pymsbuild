import py_compile
import os
import sys
from pathlib import Path, PureWindowsPath

try:
    PYC_OPTIMIZATION = int(os.getenv("PYMSBUILD_PYC_OPTIMIZE", "0"))
except ValueError:
    PYC_OPTIMIZATION = 0

RESID_COUNTER = iter(range(1001, 9999))
IMPORTERS_RESID = next(RESID_COUNTER)


def groupby(iterator, key):
    result = {}
    for i in iterator:
        result.setdefault(key(i), []).append(i)
    return result


def parse_all(file):
    g = groupby(map(str.strip, file), key=lambda i: i.partition(":")[0].lower())
    factories = dict(code=CodeFileInfo, resource=DataFileInfo, function=FunctionInfo)
    return [
        factories.get(k, ErrorInfo)(next(RESID_COUNTER), line)
        for k, v in g.items() for line in v
    ]


class CodeFileInfo:
    RC_TYPE = "PYCFILE"
    RC_TABLE = "IMPORT_TABLE"

    def __init__(self, resid, line):
        _, name, path = line.split(":", maxsplit=2)
        name = PureWindowsPath(name)
        path = Path(path)
        self.is_package = name.stem.casefold() == "__init__".casefold()
        self.name = ".".join(name.parts[:-1])
        if not self.is_package:
            self.name += "." + name.stem
        self.origin = str(name)
        self.sourcefile = path
        self._resource_file = None
        if path.suffix.casefold() == ".pyc".casefold():
            self._resource_file = self.sourcefile
        self.resid = resid

    def resource_file(self):
        if not self._resource_file:
            self._resource_file = Path(py_compile.compile(
                str(self.sourcefile),
                "pyc{}.bin".format(self.resid),
                self.origin,
                doraise=True,
                optimize=PYC_OPTIMIZATION,
                invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
            ))
        return self._resource_file

    def check(self):
        if not self.sourcefile.is_file():
            return "Missing input: {}".format(self.sourcefile)

    @classmethod
    def get_builtin(cls, resid, sourcefile):
        return cls(resid, "${}:{}".format(sourcefile.stem, sourcefile))


class DataFileInfo:
    RC_TYPE = "DATAFILE"
    RC_TABLE = "DATA_TABLE"

    def __init__(self, resid, line):
        _, name, path = line.split(":", maxsplit=2)
        name = PureWindowsPath(name)
        path = Path(path)
        self.name = ".".join(name.parts)
        self.origin = str(name)
        self.sourcefile = path
        self.resid = resid

    def check(self):
        if not self.sourcefile.is_file():
            return "Missing input: {}".format(self.sourcefile)

    def resource_file(self):
        return self.sourcefile


class FunctionInfo:
    RC_TYPE = None
    RC_TABLE = "$FUNCTIONS"

    def __init__(self, resid, line):
        self.name = line.partition(":")[2]
        self.resid = resid

    def check(self):
        if not self.name.isidentifier():
            return "Invalid name: {}".format(self.name)

    def prototype(self):
        return "PyObject *{}(PyObject *, PyObject *, PyObject *);".format(self.name)


class ErrorInfo:
    RC_TYPE = None
    RC_TABLE = None

    def __init__(self, resid, line):
        self.line = line
        self.resid = resid

    def check(self):
        return "Unhandled input: " + line


def _write_rc_string(id, s, file):
    print(id, '"', end="", file=file)
    while len(s) > 4000:
        print(s[:4000], "\\", sep="", file=file)
        s = s[4000:]
    print(s, '"', sep="", file=file)


def _c_str(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _generate_files(module, files, targets):
    files.append(CodeFileInfo.get_builtin(IMPORTERS_RESID, targets / "dllpack_main.py"))

    with open("dllpack.rc", "w", encoding="ascii", errors="backslashescape") as rc_file:
        print("#define PYCFILE 257", file=rc_file)
        print("#define DATAFILE 258", file=rc_file)
        for f in files:
            if f.RC_TYPE:
                print(f.resid, f.RC_TYPE, _c_str(f.resource_file()), file=rc_file)

    with open("dllpack.h", "w", encoding="ascii", errors="backslashescape") as h_file:
        print('#define _MODULE_NAME "{}"'.format(module), file=h_file)
        print("#define _IMPORTERS_RESID", IMPORTERS_RESID, file=h_file)
        print('#define _INIT_FUNC_NAME PyInit_{}'.format(module), file=h_file)
        print("#define _PYCFILE 257", file=h_file)
        print("#define _DATAFILE 258", file=h_file)
        print("#define _PYC_HEADER_LEN 16", file=h_file)
        print("struct ENTRY {const char *name; const char *origin; int id;};", file=h_file)
        tables = groupby(files, lambda f: f.RC_TABLE)
        for table, table_files in tables.items():
            if not table or not table.isidentifier():
                continue
            print("struct ENTRY ", table, "[] = {", sep="", file=h_file)
            for f in table_files:
                print("    {", file=h_file)
                print('        {},'.format(_c_str(f.name)), file=h_file)
                print('        {},'.format(_c_str(f.origin)), file=h_file)
                print("        {}".format(f.resid), file=h_file)
                print("    },", file=h_file)
            print("    {NULL, NULL, 0}", file=h_file)
            print("};", file=h_file)
        for f in tables.get("$FUNCTIONS", ()):
            print("extern", f.prototype(), file=h_file);
        print("#define MOD_METH_TAIL \\", file=h_file)
        for f in tables.get("$FUNCTIONS", ()):
            print('    {{"{0}", (PyCFunction){0}, METH_VARARGS|METH_KEYWORDS, NULL}}, \\'.format(f.name), file=h_file)
        print("    {NULL, NULL, 0, NULL}", file=h_file)


if __name__ == "__main__":
    import sys
    MODULE = sys.argv[1]
    with open(sys.argv[2], "r", encoding="utf-8-sig") as f:
        PARSED = parse_all(f)
    ERRORS = [p.check() for p in PARSED]
    if any(ERRORS):
        print(*filter(None, ERRORS), sep="\n")
        sys.exit(1)
    TARGETS = Path(sys.argv[3]).absolute()
    _generate_files(MODULE, PARSED, TARGETS)

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
    factories = dict(
        code=CodeFileInfo,
        resource=DataFileInfo,
        function=FunctionInfo,
        redirect=RedirectInfo,
        encrypt=EncryptInfo,
    )
    return [
        factories.get(k, ErrorInfo)(line)
        for k, v in g.items() for line in v
    ]


class CodeFileInfo:
    RC_TYPE = "PYCFILE"
    RC_TABLE = "IMPORT_TABLE"

    def __init__(self, line, resid=None):
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
        if path.match("*.pyc"):
            self._resource_file = self.sourcefile
        self.resid = next(RESID_COUNTER) if resid is None else resid

    def resource_file(self, encrypt=None):
        if not self._resource_file:
            pyc = Path(py_compile.compile(
                str(self.sourcefile),
                "pyc{}.bin".format(self.resid),
                self.origin,
                doraise=True,
                optimize=PYC_OPTIMIZATION,
                invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
            ))
            if encrypt:
                self._resource_file = Path("pycx{}.bin".format(self.resid))
                encrypt.file(src=pyc, dest=self._resource_file)
            else:
                self._resource_file = pyc
        return self._resource_file

    def check(self):
        if not self.sourcefile.is_file():
            return "Missing input: {}".format(self.sourcefile)

    @classmethod
    def get_builtin(cls, resid, sourcefile):
        return cls("code:${}:{}".format(sourcefile.stem, sourcefile), resid=resid)


class DataFileInfo:
    RC_TYPE = "DATAFILE"
    RC_TABLE = "DATA_TABLE"

    def __init__(self, line):
        _, name, path = line.split(":", maxsplit=2)
        name = PureWindowsPath(name)
        path = Path(path)
        self.name = ".".join(name.parts)
        self.origin = str(name)
        self.sourcefile = path
        self._resource_file = None
        self.resid = next(RESID_COUNTER)

    def check(self):
        if not self.sourcefile.is_file():
            return "Missing input: {}".format(self.sourcefile)

    def resource_file(self, encrypt=None):
        if self._resource_file:
            return self._resource_file
        if not encrypt:
            return self.sourcefile
        self._resource_file = Path(f"data{self.resid}.bin")
        encrypt.file(src=self.sourcefile, dest=self._resource_file)
        return self._resource_file

class FunctionInfo:
    RC_TYPE = None
    RC_TABLE = "$FUNCTIONS"
    resid = 0

    def __init__(self, line):
        self.name = line.partition(":")[2]

    def check(self):
        if not self.name.isidentifier():
            return "Invalid name: {}".format(self.name)

    def prototype(self):
        return "PyObject *{}(PyObject *, PyObject *, PyObject *);".format(self.name)


class RedirectInfo:
    RC_TYPE = None
    RC_TABLE = "REDIRECT_TABLE"
    resid = 0

    def __init__(self, line):
        _, name, self.origin = line.split(":", 2)
        if not name:
            bits = Path(self.origin).name.split(".")
            if bits and bits[-1].lower() == "pyd":
                bits.pop()
                if bits and "-win" in bits[-1].lower():
                    bits.pop()
            self.name = ".".join(bits)
        else:
            self.name = name

    def check(self):
        pass


class EncryptInfo:
    RC_TYPE = None
    RC_TABLE = None

    def __init__(self, line):
        self.name = line.partition(":")[2]
        self._key = None

    @property
    def key(self):
        if not self._key:
            key = os.getenv(self.name)
            if not key:
                raise ValueError("no key provided")
            if key.startswith("base64:"):
                import base64
                self._key = base64.b64decode(key.partition(":")[2])
            else:
                self._key = key.encode("utf-8", "strict")
        return self._key

    def check(self):
        try:
            key = self.key
            try:
                from windows.cryptography import algorithms
            except ImportError:
                from cryptography import algorithms
            if not key:
                return
            if len(key) * 8 not in algorithms.AES.key_sizes():
                return f"Key must be {algorithms.AES.key_sizes()} bits"
        except Exception as ex:
            return "Cannot use encryption key ({})".format(ex)

    def file(self, src, dest):
        try:
            from windows.cryptography import algorithms, modes, Cipher
        except ImportError:
            from cryptography import algorithms, modes, Cipher
        block_size = algorithms.AES.block_sizes()[0]
        iv = os.urandom(block_size)
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        bufs = []
        with open(src, "rb") as f1:
            eof = False
            while not eof:
                buf = f1.read(cipher.block_length)
                eof = not buf
                buf = encryptor.update(buf) if buf else encryptor.finalize()
                if buf:
                    bufs.append(buf)
        with open(dest, "wb") as f2:
            f2.write(os.stat(src).st_size.to_bytes(4, "little"))
            f2.write(sum(len(b) for b in bufs).to_bytes(4, "little"))
            f2.write(len(iv).to_bytes(4, "little"))
            f2.write(iv)
            for buf in bufs:
                f2.write(buf)

    @classmethod
    def find_key(cls, items):
        return next((p for p in items if isinstance(p, cls)), None)


class ErrorInfo:
    RC_TYPE = None
    RC_TABLE = None

    def __init__(self, line):
        self.line = line

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


def _generate_files(module, files, targets, encrypt=None):
    files.append(CodeFileInfo.get_builtin(IMPORTERS_RESID, targets / "dllpack_main.py"))

    with open("dllpack.rc", "w", encoding="ascii", errors="backslashescape") as rc_file:
        print("#define PYCFILE 257", file=rc_file)
        print("#define DATAFILE 258", file=rc_file)
        for f in files:
            if f.RC_TYPE:
                print(f.resid, f.RC_TYPE, _c_str(f.resource_file(encrypt)), file=rc_file)

    with open("dllpack.h", "w", encoding="ascii", errors="backslashescape") as h_file:
        print('#define _MODULE_NAME "{}"'.format(module), file=h_file)
        print("#define _IMPORTERS_RESID", IMPORTERS_RESID, file=h_file)
        print('#define _INIT_FUNC_NAME PyInit_{}'.format(module), file=h_file)
        print("#define _PYCFILE 257", file=h_file)
        print("#define _DATAFILE 258", file=h_file)
        print("#define _PYC_HEADER_LEN 16", file=h_file)
        if encrypt:
            print('#define _ENCRYPT_KEY_NAME L"{}"'.format(encrypt.name), file=h_file)
        print("struct ENTRY {const char *name; const char *origin; int id;};", file=h_file)
        expected_tables = {"IMPORT_TABLE", "DATA_TABLE", "REDIRECT_TABLE"}
        tables = groupby(files, lambda f: f.RC_TABLE)
        for table, table_files in tables.items():
            if not table or not table.isidentifier():
                continue
            expected_tables.discard(table)
            print("struct ENTRY ", table, "[] = {", sep="", file=h_file)
            for f in sorted(table_files, key=lambda i: i.name):
                print("    {", file=h_file)
                print('        {},'.format(_c_str(f.name)), file=h_file)
                print('        {},'.format(_c_str(f.origin)), file=h_file)
                print("        {}".format(f.resid), file=h_file)
                print("    },", file=h_file)
            print("    {NULL, NULL, 0}", file=h_file)
            print("};", file=h_file)
        for table in expected_tables:
            print("struct ENTRY ", table, "[] = {{NULL, NULL, 0}};", sep="", file=h_file)
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
    ENCRYPT = EncryptInfo.find_key(PARSED)
    TARGETS = Path(sys.argv[3]).absolute()
    _generate_files(MODULE, PARSED, TARGETS, ENCRYPT)

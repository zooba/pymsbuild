import py_compile
import os
import sys
from importlib.machinery import EXTENSION_SUFFIXES
from pathlib import Path, PurePath

try:
    PYC_OPTIMIZATION = int(os.getenv("PYMSBUILD_PYC_OPTIMIZE", "0"))
except ValueError:
    PYC_OPTIMIZATION = 0

RESID_COUNTER = iter(range(1001, 999999))
IMPORTERS_RESID = next(RESID_COUNTER)


def groupby(iterator, key):
    result = {}
    for i in iterator:
        result.setdefault(key(i), []).append(i)
    return result


def parse_all(file):
    g = groupby(map(str.strip, file), key=lambda i: i.partition(":")[0].lower())
    factories = dict(
        module=ModuleInfo,
        platform=PlatformInfo,
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


class ModuleInfo:
    RC_TYPE = None
    RC_TABLE = None

    def __init__(self, line):
        _, self.from_module, self.module = line.split(":", 3)
        if self.module:
            bits = self.module.split(".")
            for i in reversed(range(len(bits))):
                if not bits[i].isidentifier():
                    bits = bits[i + 1:]
                    break
            self.module = ".".join(bits)

    def check(self):
        pass

    @classmethod
    def find(cls, items, default):
        for i in items:
            if isinstance(i, cls):
                return i.from_module, i.module
        return default, default


class PlatformInfo:
    RC_TYPE = None
    RC_TABLE = None

    def __init__(self, line):
        self.platform = line.partition(":")[2].lower()

    def check(self):
        if self.platform not in {"windows", "gcc"}:
            return "Unsupported platform"

    @classmethod
    def find(cls, items, default="windows"):
        for i in items:
            if isinstance(i, cls):
                err = i.check()
                if err:
                    raise ValueError(err)
                return i.platform
        return default


class CodeFileInfo:
    RC_TYPE = "PYCFILE"
    RC_TABLE = "IMPORT_TABLE"

    def __init__(self, line, resid=None):
        _, name, path = line.split(":", maxsplit=2)
        name = PurePath(name)
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

    def remap_namespace(self, from_name, to_name):
        if self.name.startswith(from_name + "."):
            self.name = to_name + self.name[len(from_name):]

    @classmethod
    def get_builtin(cls, resid, sourcefile, name):
        return cls("code:${}:{}".format(name or sourcefile.stem, sourcefile), resid=resid)


class DataFileInfo:
    RC_TYPE = "DATAFILE"
    RC_TABLE = "DATA_TABLE"
    is_package = False

    def __init__(self, line):
        _, name, path = line.split(":", maxsplit=2)
        name = PurePath(name)
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
        self._resource_file = Path(f"data{self.resid}.bin")
        if encrypt:
            encrypt.file(src=self.sourcefile, dest=self._resource_file)
        else:
            self._resource_file.write_bytes(self.sourcefile.read_bytes())
        return self._resource_file

    def remap_namespace(self, from_name, to_name):
        if self.name.startswith(from_name + "."):
            self.name = to_name + self.name[len(from_name):]


class FunctionInfo:
    RC_TYPE = None
    RC_TABLE = "$FUNCTIONS"
    resid = 0
    is_package = False

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
    is_package = False

    def __init__(self, line):
        _, name, self.origin, root = line.split(":", 3)
        if not name or name.endswith("."):
            name = name or ""
            p = Path(self.origin)
            for ext in sorted(EXTENSION_SUFFIXES, reverse=True, key=len):
                if p.match(f"*{ext}"):
                    self.name = name + p.name[:-len(ext)]
                    break
            else:
                self.name = name + p.name
            if not name and root:
                root_bits = []
                name_bits = self.name.split(".")
                for r in reversed(root.split(".")):
                    if not r.isidentifier():
                        break
                    root_bits.insert(0, r)
                if name_bits[:len(root_bits)] != root_bits:
                    self.name = ".".join([*root_bits, *name_bits])
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
                key_sizes = algorithms.AES.key_sizes()
            except ImportError:
                try:
                    from cryptography.hazmat.primitives.ciphers import algorithms
                except ImportError:
                    return "No supported cryptography libraries available"
                key_sizes = [128, 192, 256]
            if not key:
                return
            if len(key) * 8 not in key_sizes:
                return f"Key must be {key_sizes} bits"
        except Exception as ex:
            return "Cannot use encryption key ({})".format(ex)

    def file(self, src, dest):
        try:
            from windows.cryptography import algorithms, modes, Cipher
            block_size = algorithms.AES.block_sizes()[0]
            padder = None
        except ImportError:
            from cryptography.hazmat.primitives import padding
            from cryptography.hazmat.primitives.ciphers import algorithms, modes, Cipher
            block_size = 16
            padder = padding.PKCS7(block_size * 8).padder()
        iv = os.urandom(block_size)
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        bufs = []
        with open(src, "rb") as f1:
            eof = False
            while not eof:
                buf = f1.read(8192)
                eof = not buf
                if padder:
                    buf = padder.update(buf) if buf else padder.finalize()
                if buf:
                    bufs.append(buf)
        bufs = [encryptor.update(b) for b in bufs]
        bufs.append(encryptor.finalize())
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
        return "Unhandled input: " + self.line


def _write_rc_string(id, s, file):
    print(id, '"', end="", file=file)
    while len(s) > 4000:
        print(s[:4000], "\\", sep="", file=file)
        s = s[4000:]
    print(s, '"', sep="", file=file)


def _c_str(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _generate_windows_files(module, files, targets, encrypt=None):
    files.append(CodeFileInfo.get_builtin(IMPORTERS_RESID, targets / "dllpack_main.py", f"dllpack.{module}"))

    module_name = module.rpartition(".")[2]

    with open("dllpack.rc", "w", encoding="ascii", errors="backslashescape") as rc_file:
        print("#define PYCFILE 257", file=rc_file)
        print("#define DATAFILE 258", file=rc_file)
        for f in files:
            if f.RC_TYPE:
                print(f.resid, f.RC_TYPE, _c_str(f.resource_file(encrypt)), file=rc_file)

    with open("dllpack.h", "w", encoding="ascii", errors="backslashescape") as h_file:
        print('#define _MODULE_NAME "{}"'.format(module), file=h_file)
        print('#define _INIT_FUNC_NAME PyInit_{}'.format(module_name), file=h_file)
        print("#define _PYCFILE 257", file=h_file)
        print("#define _DATAFILE 258", file=h_file)
        print("#define _PYC_HEADER_LEN 16", file=h_file)
        if encrypt:
            print('#define _ENCRYPT_KEY_NAME L"{}"'.format(encrypt.name), file=h_file)
        print('#include "dllpack-windows.h"', file=h_file)
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
                print("        {},".format(f.resid), file=h_file)
                print("        {}".format(1 if f.is_package else 0), file=h_file)
                print("    },", file=h_file)
            print("    {NULL, NULL, 0}", file=h_file)
            print("};", file=h_file)
        print(f"struct ENTRY _IMPORTERS = {{NULL, NULL, {IMPORTERS_RESID}, 0}};", file=h_file)
        for table in expected_tables:
            print("struct ENTRY ", table, "[] = {{NULL, NULL, 0, 0}};", sep="", file=h_file)
        for f in tables.get("$FUNCTIONS", ()):
            print("extern", f.prototype(), file=h_file);
        print("#define MOD_METH_TAIL \\", file=h_file)
        for f in tables.get("$FUNCTIONS", ()):
            print('    {{"{0}", (PyCFunction){0}, METH_VARARGS|METH_KEYWORDS, NULL}}, \\'.format(f.name), file=h_file)
        print("    {NULL, NULL, 0, NULL}", file=h_file)


def _generate_gcc_files(module, files, targets, encrypt=None):
    importer = CodeFileInfo.get_builtin(IMPORTERS_RESID, targets / "dllpack_main.py", f"dllpack.{module}")
    files.append(importer)

    module_name = module.rpartition(".")[2]

    with open("dllpack.rc", "w", encoding="utf-8", errors="strict") as rc_file:
        for f in files:
            if f.RC_TYPE:
                print(f.resource_file(encrypt), file=rc_file)

    with open("dllpack.h", "w", encoding="ascii", errors="backslashescape") as h_file:
        print('#define _MODULE_NAME "{}"'.format(module), file=h_file)
        print('#define _INIT_FUNC_NAME PyInit_{}'.format(module_name), file=h_file)
        print("#define _PYC_HEADER_LEN 16", file=h_file)
        print('#include "dllpack-gcc.h"', file=h_file)
        if encrypt:
            print('#define _ENCRYPT_KEY_NAME L"{}"'.format(encrypt.name), file=h_file)
        expected_tables = {"IMPORT_TABLE", "DATA_TABLE", "REDIRECT_TABLE"}
        for f in files:
            if f.RC_TYPE:
                res_name = f.resource_file(encrypt).name.replace(".", "_")
                print(f"_IMPORT_DATA({res_name})", file=h_file)
        tables = groupby(files, lambda f: f.RC_TABLE)
        for table, table_files in tables.items():
            if not table or not table.isidentifier():
                continue
            expected_tables.discard(table)
            print("struct ENTRY ", table, "[] = {", sep="", file=h_file)
            for f in sorted(table_files, key=lambda i: i.name):
                if f.RC_TYPE:
                    res_name = "_REFERENCE_DATA({})".format(
                        f.resource_file(encrypt).name.replace(".", "_")
                    )
                else:
                    res_name = "NULL"
                print("    {", file=h_file)
                print("        {},".format(_c_str(f.name)), file=h_file)
                print("        {},".format(_c_str(f.origin)), file=h_file)
                print("        {},".format(res_name), file=h_file)
                print("        {}".format(1 if f.is_package else 0), file=h_file)
                print("    },", file=h_file)
            print("    {NULL, NULL, NULL}", file=h_file)
            print("};", file=h_file)
        res_name = importer.resource_file(encrypt).name.replace(".", "_")
        print(f"struct ENTRY _IMPORTERS = {{_MODULE_NAME, _MODULE_NAME, _REFERENCE_DATA({res_name}), 0}};", file=h_file)
        for table in expected_tables:
            print("struct ENTRY ", table, "[] = {{NULL, NULL, NULL, 0}};", sep="", file=h_file)
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
    FROM_MODULE, MODULE = ModuleInfo.find(PARSED, MODULE)
    PLATFORM = PlatformInfo.find(PARSED)
    ENCRYPT = EncryptInfo.find_key(PARSED)
    TARGETS = Path(sys.argv[3]).absolute()
    GENERATOR = {
        "windows": _generate_windows_files,
        "gcc": _generate_gcc_files,
    }[PLATFORM]
    if FROM_MODULE != MODULE:
        for f in PARSED:
            try:
                f.remap_namespace(FROM_MODULE, MODULE)
            except AttributeError:
                pass
    GENERATOR(MODULE, PARSED, TARGETS, ENCRYPT)

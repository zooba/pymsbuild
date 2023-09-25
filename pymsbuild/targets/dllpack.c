#include <windows.h>
#include "Python.h"
#include "marshal.h"
#include "dllpack.h"

#define STATUS_DATA_ERROR 0xC000003E

static HMODULE hInstance;

#ifdef _ENCRYPT_KEY_NAME
static const wchar_t *encrypt_variable = _ENCRYPT_KEY_NAME;
#else
static const wchar_t *encrypt_variable = NULL;
#endif

typedef struct {
    BCRYPT_ALG_HANDLE hAlg;
    BCRYPT_KEY_HANDLE hKey;
} ModuleState;


static const struct ENTRY *
lookup_import(const char *name, int *is_package)
{
    struct ENTRY *found = NULL;
    int cchName = strlen(name);
    *is_package = 0;
    if (PySys_Audit("pymsbuild.dllpack.lookup_import", "ss", _DLLPACK_NAME, name) < 0) {
        return NULL;
    }
    for (struct ENTRY *entry = IMPORT_TABLE; entry->name; ++entry) {
        if (!strcmp(entry->name, name)) {
            found = entry;
        }
        if (!strncmp(entry->name, name, cchName) && entry->name[cchName] == '.') {
            *is_package = 1;
            if (found) {
                break;
            }
        }
    }
    return found;
}

static const struct ENTRY *
lookup_data(const char *name)
{
    if (PySys_Audit("pymsbuild.dllpack.lookup_data", "ss", _DLLPACK_NAME, name) < 0) {
        return NULL;
    }
    for (struct ENTRY *entry = DATA_TABLE; entry->name; ++entry) {
        if (!strcmp(entry->name, name)) {
            return entry;
        }
    }
    return NULL;
}

static const struct ENTRY *
lookup_redirect(const char *name)
{
    if (PySys_Audit("pymsbuild.dllpack.lookup_redirect", "ss", _DLLPACK_NAME, name) < 0) {
        return NULL;
    }
    for (struct ENTRY *entry = REDIRECT_TABLE; entry->name; ++entry) {
        if (!strcmp(entry->name, name)) {
            return entry;
        }
    }
    return NULL;
}

static void *
decrypt_buffer(ModuleState *ms, const char **buffer, DWORD *cbBuffer)
{
    struct hdr {
        DWORD cbPlain;
        DWORD cbData;
        DWORD cbIV;
        const UCHAR iv[512];
    } *header = (struct hdr*)*buffer;
    UCHAR iv[512];
    if (PySys_Audit("pymsbuild.dllpack.decrypt_buffer", "III", header->cbData, header->cbPlain, header->cbIV) < 0) {
        return NULL;
    }
    if (header->cbIV > sizeof(iv)) {
        PyErr_Format(PyExc_OverflowError, "requested IV length (%i) is too large", header->cbIV);
        return NULL;
    }
    memcpy(iv, header->iv, header->cbIV);
    PUCHAR data = (PUCHAR)&header->iv[header->cbIV];
    DWORD cbPlainActual;
    PUCHAR plain = (PUCHAR)HeapAlloc(GetProcessHeap(), HEAP_GENERATE_EXCEPTIONS, header->cbPlain);

    NTSTATUS err = BCryptDecrypt(
        ms->hKey,
        data, header->cbData,
        NULL,
        iv, header->cbIV,
        plain, header->cbPlain,
        &cbPlainActual,
        BCRYPT_BLOCK_PADDING
    );
    if (err) {
        HeapFree(GetProcessHeap(), 0, plain);
        if (err == STATUS_DATA_ERROR) {
            PyErr_SetString(PyExc_ImportError, "Failed to decode module");
        } else {
            PyErr_SetFromWindowsErr(err);
        }
        return NULL;
    }

    *buffer = (const char *)plain;
    *cbBuffer = cbPlainActual;
    return plain;
}

static void
free_decrypt_cookie(void *cookie)
{
    HeapFree(GetProcessHeap(), 0, cookie);
}


static PyObject *
load_bytes(ModuleState *ms, int id)
{
    if (PySys_Audit("pymsbuild.dllpack.load_bytes", "si", _DLLPACK_NAME, id) < 0) {
        return NULL;
    }
    PyObject *obj;
    HRSRC block = FindResourceW(hInstance, MAKEINTRESOURCE(id), MAKEINTRESOURCE(_DATAFILE));
    if (!block) {
        PyErr_SetFromWindowsErr(GetLastError());
        return NULL;
    }
    DWORD cbBuffer = SizeofResource(hInstance, block);
    if (!cbBuffer) {
        PyErr_SetFromWindowsErr(GetLastError());
        return NULL;
    }
    HGLOBAL res = LoadResource(hInstance, block);
    if (!res) {
        PyErr_SetFromWindowsErr(GetLastError());
        return NULL;
    }
    const char *buffer = (const char*)LockResource(res);
    if (!buffer) {
        PyErr_SetFromWindowsErr(GetLastError());
        FreeResource(res);
        return NULL;
    }
    void *decrypt_cookie = NULL;
    if (encrypt_variable) {
        decrypt_cookie = decrypt_buffer(ms, &buffer, &cbBuffer);
        if (!decrypt_cookie) {
            FreeResource(res);
            return NULL;
        }
    }
    obj = PyBytes_FromStringAndSize(buffer, cbBuffer);
    FreeResource(res);
    free_decrypt_cookie(decrypt_cookie);
    return obj;
}

static PyObject *
load_pyc(ModuleState *ms, int id)
{
    if (PySys_Audit("pymsbuild.dllpack.load_pyc", "si", _DLLPACK_NAME, id) < 0) {
        return NULL;
    }
    PyObject *obj;
    HRSRC block = FindResourceW(hInstance, MAKEINTRESOURCE(id), MAKEINTRESOURCE(_PYCFILE));
    if (!block) {
        PyErr_SetFromWindowsErr(GetLastError());
        return NULL;
    }
    DWORD cbBuffer = SizeofResource(hInstance, block);
    if (!cbBuffer) {
        PyErr_SetFromWindowsErr(GetLastError());
        return NULL;
    }
    HGLOBAL res = LoadResource(hInstance, block);
    if (!res) {
        PyErr_SetFromWindowsErr(GetLastError());
        return NULL;
    }
    const char *buffer = (const char*)LockResource(res);
    if (!buffer) {
        PyErr_SetFromWindowsErr(GetLastError());
        FreeResource(res);
        return NULL;
    }
    void *decrypt_cookie = NULL;
    if (encrypt_variable) {
        decrypt_cookie = decrypt_buffer(ms, &buffer, &cbBuffer);
        if (!decrypt_cookie) {
            FreeResource(res);
            return NULL;
        }
    }
    // Our .pyc has a header
    obj = PyMarshal_ReadObjectFromString(&buffer[_PYC_HEADER_LEN], cbBuffer - _PYC_HEADER_LEN);
    FreeResource(res);
    free_decrypt_cookie(decrypt_cookie);
    return obj;
}

static PyObject*
get_origin_root()
{
    wchar_t buff[256];
    DWORD cch = GetModuleFileNameW(hInstance, buff, sizeof(buff) / sizeof(buff[0]));
    if (cch == 0) {
        PyErr_SetFromWindowsErr(GetLastError());
        return NULL;
    } else if (cch < sizeof(buff) / sizeof(buff[0])) {
        while (cch && buff[cch - 1] != '\\' && buff[cch - 1] != '/') {
            --cch;
        }
        return PyUnicode_FromWideChar(buff, cch);
    }
    cch += 1;
    wchar_t *buff2 = (wchar_t *)PyMem_Malloc(sizeof(wchar_t) * cch);
    if (!buff2) {
        return NULL;
    }
    DWORD cch2 = GetModuleFileNameW(hInstance, buff2, cch);
    PyObject *r = NULL;
    if (cch2 == 0) {
        PyErr_SetFromWindowsErr(GetLastError());
    } else if (cch2 >= cch) {
        PyErr_SetString(PyExc_SystemError, "failed to get DLL name; cannot import");
    } else {
        while (cch2 & buff2[cch2 - 1] != '\\' && buff2[cch2 - 1] != '/') {
            --cch2;
        }
        r = PyUnicode_FromWideChar(buff2, cch2);
    }
    PyMem_Free(buff2);
    return r;
}

static PyObject *
mod_load_impl(ModuleState *ms, const char *name, PyObject *mod, int is_main) {
    int is_package = 0;
    const struct ENTRY *e = lookup_import(name, &is_package);
    if (!e) {
        PyErr_Format(PyExc_ModuleNotFoundError, "'%s' is not part of this package", name);
        return NULL;
    }
    if (e->id == 0) {
        PyErr_Format(PyExc_ModuleNotFoundError, "unable to import '%s'", name);
        return NULL;
    }

    PyObject *pyc, *r;
    if (is_main) {
        pyc = load_pyc(ms, _IMPORTERS_RESID);
        if (!pyc) {
            return NULL;
        }
        r = PyImport_ExecCodeModule(name, pyc);
        Py_DECREF(pyc);
        if (!r) {
            return NULL;
        }
        Py_DECREF(r);
    }

    pyc = load_pyc(ms, e->id);
    if (!pyc) {
        return NULL;
    }

    PyObject *spec = PyObject_GetAttrString(mod, "__spec__");
    PyObject *oname = spec ? PyObject_GetAttrString(spec, "name") : NULL;
    PyObject *origin = spec ? PyObject_GetAttrString(spec, "origin") : NULL;
    if (oname && origin) {
        r = PyImport_ExecCodeModuleObject(oname, pyc, origin, NULL);
    } else {
        PyErr_Clear();
        r = PyImport_ExecCodeModule(name, pyc);
    }
    Py_XDECREF(spec);
    Py_XDECREF(oname);
    Py_XDECREF(origin);
    Py_DECREF(pyc);
    if (!r) {
        return NULL;
    }
    Py_DECREF(r);
    return mod;
}

static PyObject *
mod_load(PyObject *self, PyObject *args)
{
    PyObject *mod = NULL;
    if (!PyArg_ParseTuple(args, "O", &mod)) {
        return NULL;
    }
    mod = mod_load_impl((ModuleState*)PyModule_GetState(self), PyModule_GetName(mod), mod, 0);
    Py_XINCREF(mod);
    return mod;
}

static PyObject *
mod_new(PyObject *self, PyObject *args)
{
    PyObject *spec;
    if (!PyArg_ParseTuple(args, "O", &spec)) {
        return NULL;
    }
    PyObject *o = PyObject_GetAttrString(spec, "name");
    if (!o) {
        return NULL;
    }
    PyObject *mod = PyImport_AddModuleObject(o);
    if (!mod) {
        Py_DECREF(o);
        return NULL;
    }
    Py_INCREF(mod);
    if (PyModule_AddObject(mod, "__name__", o) < 0) {
        Py_DECREF(o);
        Py_DECREF(mod);
        return NULL;
    }
    // o reference has been consumed, so no DECREF needed
    o = PyObject_GetAttrString(spec, "parent");
    if (o) {
        if (o != Py_None) {
            if (PyModule_AddObject(mod, "__package__", o) < 0) {
                Py_DECREF(o);
                Py_DECREF(mod);
                return NULL;
            }
            // o reference has been consumed
        } else {
            Py_DECREF(o);
        }
    } else {
        PyErr_Clear();
    }
    o = PyObject_GetAttrString(spec, "origin");
    if (o) {
        if (PyModule_AddObject(mod, "__file__", o) < 0) {
            Py_DECREF(o);
            Py_DECREF(mod);
            return NULL;
        }
        // o reference has been consumed
    } else {
        PyErr_Clear();
    }
    o = PyObject_GetAttrString(spec, "loader");
    if (o) {
        if (PyModule_AddObject(mod, "__loader__", o) < 0) {
            Py_DECREF(o);
            Py_DECREF(mod);
            return NULL;
        }
        // o reference has been consumed
    } else {
        PyErr_Clear();
    }
    o = PyObject_GetAttrString(spec, "submodule_search_locations");
    if (o) {
        if (PyModule_AddObject(mod, "__path__", o) < 0) {
            Py_DECREF(o);
            Py_DECREF(mod);
            return NULL;
        }
        // o reference has been consumed
    } else {
        PyErr_Clear();
    }
    return mod;
}

static PyObject *
mod_makespec(PyObject *self, PyObject *args)
{
    const char *name;
    PyObject *loader;
    if (!PyArg_ParseTuple(args, "sO", &name, &loader)) {
        return NULL;
    }

    if (PySys_Audit("pymsbuild.dllpack.makespec", "ssO", _DLLPACK_NAME, name, loader) < 0) {
        goto error;
    }

    PyObject *ilib_m = NULL, *mspec = NULL, *kwargs = NULL, *origin = NULL, *r = NULL;
    ilib_m = PyImport_ImportModule("importlib.machinery");
    if (!ilib_m) {
        goto error;
    }
    mspec = PyObject_GetAttrString(ilib_m, "ModuleSpec");
    if (!mspec) {
        goto error;
    }
    kwargs = PyDict_New();
    if (!kwargs) {
        goto error;
    }

    int is_package = 0;
    const struct ENTRY *e = lookup_import(name, &is_package);
    if (!e) {
        if (PyErr_Occurred()) {
            goto error;
        }
        e = lookup_redirect(name);
        if (!e) {
            if (!PyErr_Occurred()) {
                r = Py_None;
                Py_INCREF(r);
            }
            goto error;
        }
        args = Py_BuildValue("sO", name, Py_None);
        if (!args) {
            goto error;
        }
    }
    origin = PyObject_GetAttrString(self, "_origin_root");
    if (!origin) {
        PyErr_Clear();
        origin = get_origin_root();
        if (origin) {
            if (PySys_Audit("pymsbuild.dllpack.get_origin_root", "sO", _DLLPACK_NAME, origin) < 0) {
                goto error;
            }
            if (PyObject_SetAttrString(self, "_origin_root", origin) < 0) {
                goto error;
            }
        }
    }
    if (origin) {
        Py_SETREF(origin, PyUnicode_FromFormat("%U%s", origin, e->origin));
    }
    if (!origin) {
        goto error;
    }
    if (PyDict_SetItemString(kwargs, "origin", origin) < 0) {
        goto error;
    }
    if (is_package) {
        if (PyDict_SetItemString(kwargs, "is_package", Py_True) < 0) {
            goto error;
        }
    }

    r = PyObject_Call(mspec, args, kwargs);
error:
    Py_XDECREF(origin);
    Py_XDECREF(kwargs);
    Py_XDECREF(mspec);
    Py_XDECREF(ilib_m);

    return r;
}

static PyObject *
mod_data(PyObject *self, PyObject *args)
{
    const char *name;
    if (!PyArg_ParseTuple(args, "s", &name)) {
        return NULL;
    }
    const struct ENTRY *e = lookup_data(name);
    if (e) {
        ModuleState *ms = (ModuleState*)PyModule_GetState(self);
        return load_bytes(ms, e->id);
    }
    PyErr_Format(PyExc_FileNotFoundError, "'%s' is not part of this package", name);
    return NULL;
}

static PyObject *
mod_data_names(PyObject *self, PyObject *args)
{
    PyObject *r = PyList_New(0);
    if (!r) {
        return NULL;
    }
    if (PySys_Audit("pymsbuild.dllpack.data_names", "s", _DLLPACK_NAME) < 0) {
        return NULL;
    }
    for (struct ENTRY *entry = DATA_TABLE; entry->name; ++entry) {
        PyObject *o = PyUnicode_FromString(entry->name);
        if (!o) {
            Py_DECREF(r);
            return NULL;
        }
        if (PyList_Append(r, o) < 0) {
            Py_DECREF(r);
            Py_DECREF(o);
            return NULL;
        }
    }
    return r;
}

static PyObject*
mod_name(PyObject *self, PyObject *args)
{
    return PyUnicode_FromString(_MODULE_NAME);
}

static int
init_decryptor(ModuleState *ms)
{
    char key[4096];
    DWORD cbKey = sizeof(key);
    wchar_t buffer[4096];
    NTSTATUS err;

    ms->hAlg = NULL;
    ms->hKey = NULL;

    if (GetEnvironmentVariableW(encrypt_variable, buffer, 4096) == 0) {
        PyErr_SetFromWindowsErr(GetLastError());
        return -1;
    }
    if (0 == wcsncmp(buffer, L"base64:", 7)) {
        if (!CryptStringToBinaryW(&buffer[7], 0, CRYPT_STRING_BASE64, key, &cbKey, NULL, NULL)) {
            PyErr_SetFromWindowsErr(GetLastError());
            return -1;
        }
    } else {
        cbKey = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, buffer, -1, key, cbKey, NULL, NULL);
        if (!cbKey) {
            PyErr_SetFromWindowsErr(GetLastError());
            return -1;
        }
        cbKey -= 1;
    }

    err = BCryptOpenAlgorithmProvider(&ms->hAlg, BCRYPT_AES_ALGORITHM, NULL, 0);
    if (!err) {
        err = BCryptSetProperty(
            ms->hAlg,
            BCRYPT_CHAINING_MODE,
            (PUCHAR)BCRYPT_CHAIN_MODE_CBC,
            -1,
            0
        );
    }
    if (!err) {
        err = BCryptGenerateSymmetricKey(ms->hAlg, &ms->hKey, NULL, 0, key, cbKey, 0);
    }
    if (err) {
        PyErr_SetFromWindowsErr(err);
        return -1;
    }
    return 0;
}

static int
free_decryptor(ModuleState *ms)
{
    if (ms->hKey) {
        BCryptDestroyKey(ms->hKey);
        ms->hKey = NULL;
    }
    if (ms->hAlg) {
        BCryptCloseAlgorithmProvider(ms->hAlg, 0);
        ms->hAlg = NULL;
    }
    return 0;
}

static int
mod_exec(PyObject *m)
{
    ModuleState *ms = (ModuleState *)PyModule_GetState(m);
    if (encrypt_variable) {
        if (init_decryptor(ms) < 0) {
            free_decryptor(ms);
            return -1;
        }
    }
    return mod_load_impl(ms, PyModule_GetName(m), m, 1) ? 0 : -1;
}

static void
mod_free(PyObject *m)
{
    free_decryptor((ModuleState *)PyModule_GetState(m));
}


static struct PyMethodDef mod_meth[] = {
    {"__NAME", mod_name, METH_NOARGS, NULL},
    {"__MAKESPEC", mod_makespec, METH_VARARGS, NULL},
    {"__DATA", mod_data, METH_VARARGS, NULL},
    {"__DATA_NAMES", mod_data_names, METH_NOARGS, NULL},
    {"__CREATE_MODULE", mod_new, METH_VARARGS, NULL},
    {"__EXEC_MODULE", mod_load, METH_VARARGS, NULL},
    MOD_METH_TAIL
};

static struct PyModuleDef_Slot mod_slots[] = {
    {Py_mod_exec, mod_exec},
    {0, NULL},
};

static struct PyModuleDef modmodule = {
    PyModuleDef_HEAD_INIT,
    _MODULE_NAME,
    NULL,
    sizeof(ModuleState),
    mod_meth,
    mod_slots,
    NULL,
    NULL,
    (freefunc)mod_free
};


PyMODINIT_FUNC
_INIT_FUNC_NAME(void)
{
    return PyModuleDef_Init(&modmodule);
}

BOOL WINAPI
DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpReserved)
{
    switch( fdwReason )
    {
        case DLL_PROCESS_ATTACH:
            hInstance = hinstDLL;
            break;
        case DLL_THREAD_ATTACH:
            break;
        case DLL_THREAD_DETACH:
            break;
        case DLL_PROCESS_DETACH:
            break;
    }
    return TRUE;
}

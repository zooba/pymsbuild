#include <windows.h>
#include "Python.h"
#include "marshal.h"
#include "dllpack.h"

static HMODULE hInstance;

static int
ascii_eq_wide(const char *x, const wchar_t *y, int cch_y)
{
    int i = 0;
    while (i < cch_y) {
        if ((int)*x != (int)*y) {
            return 0;
        }
        ++x;
        ++y;
        ++i;
    }
    return 1;
}

static int
lookup_name_id(const char *name)
{
    const wchar_t *buffer;
    int cchBuffer;
    printf("Finding %s\n", name);
    for (UINT id = _FIRST_NAME_RES_ID; id < _FIRST_NAME_RES_ID + _MODULE_COUNT; ++id) {
        int is_match = 0;
        HRSRC block = FindResourceW(hInstance, MAKEINTRESOURCE((id >> 4) + 1), RT_STRING);
        if (!block) {
            PyErr_SetFromWindowsErr(GetLastError());
            return -1;
        }
        HGLOBAL res = LoadResource(hInstance, block);
        if (!res) {
            PyErr_SetFromWindowsErr(GetLastError());
            return -1;
        }
        const wchar_t *buffer = (const wchar_t*)LockResource(res);
        if (!buffer) {
            PyErr_SetFromWindowsErr(GetLastError());
            FreeResource(res);
            return -1;
        }
        ptrdiff_t off = 0;
        for (UINT i = id & 0xF; i; --i) {
            off += buffer[off] + 1;
        }
        printf("Checking %i: %ls (%i)\n", id, &buffer[off + 1], (int)buffer[off]);
        is_match = ascii_eq_wide(name, &buffer[off + 1], (int)buffer[off]);
        UnlockResource(buffer);
        FreeResource(res);
        if (is_match) {
            return id - _FIRST_NAME_RES_ID + 1;
        }
    }
    return 0;
}

static PyObject *
load_pyc(int id)
{
    PyObject *pyc_obj;
    HRSRC block = FindResourceW(hInstance, MAKEINTRESOURCE(id + _FIRST_PYC_RES_ID - 1), MAKEINTRESOURCE(_PYCFILE));
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
    pyc_obj = PyMarshal_ReadObjectFromString(&buffer[16], (Py_ssize_t)cbBuffer - 16);
    UnlockResource(buffer);
    FreeResource(res);
    return pyc_obj;
}

static int
mod_exec(PyObject *m)
{
    if (_MODULE_COUNT) {
        // TODO: Set up import hook for submodules
    }

    int id = lookup_name_id(_MODULE_NAME ".__init__");
    if (id < 0) {
        return -1;
    } else if (id > 0) {
        PyObject *pyc = load_pyc(id);
        if (!pyc) {
            return -1;
        }
        PyObject *mod = PyImport_ExecCodeModule(_MODULE_NAME, pyc);
        if (!mod) {
            Py_DECREF(pyc);
            return -1;
        }
        Py_SETREF(mod, PyObject_Repr(mod));
        Py_DECREF(mod);
        Py_DECREF(pyc);
    }
    return 0;
}

static struct PyModuleDef_Slot mod_slots[] = {
    {Py_mod_exec, mod_exec},
    {0, NULL},
};

static struct PyModuleDef modmodule = {
    PyModuleDef_HEAD_INIT,
    _MODULE_NAME,
    NULL,
    0,
    NULL,
    mod_slots,
    NULL,
    NULL,
    NULL
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

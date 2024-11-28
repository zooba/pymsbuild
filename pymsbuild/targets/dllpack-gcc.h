#define PY_SSIZE_T_CLEAN
#define _GNU_SOURCE 1
#include <dlfcn.h>

#include "Python.h"
#include "marshal.h"

typedef int (*_GET_DATA)(const char **start, Py_ssize_t *end);

#define _IMPORT_DATA(name) \
static int _get_data_ ## name(const char **start, Py_ssize_t *size) { \
    extern const char _binary_ ## name ## _start[]; \
    extern const char _binary_ ## name ## _end[]; \
    *start = _binary_ ## name ## _start; \
    *size = (Py_ssize_t)((_binary_ ## name ## _end) - (_binary_ ## name ## _start)); \
    return *start != NULL; \
}

#define _REFERENCE_DATA(name) _get_data_ ## name

struct ENTRY {
    const char *name;
    const char *origin;
    _GET_DATA get;
    char is_package;
};

typedef struct {
} ModuleState;


static PyObject *
load_bytes(ModuleState *ms, const struct ENTRY *entry)
{
    const char *buffer;
    Py_ssize_t cbBuffer;
    if (!entry->get || !entry->get(&buffer, &cbBuffer)) {
        PyErr_Format(PyExc_ModuleNotFoundError, "unable to open '%s'", entry->origin);
        return NULL;
    }
    if (PySys_Audit("pymsbuild.dllpack.load_bytes", "ss", _DLLPACK_NAME, entry->origin) < 0) {
        return NULL;
    }
    return PyBytes_FromStringAndSize(buffer, cbBuffer);
}


static PyObject *
load_pyc(ModuleState *ms, const struct ENTRY *entry)
{
    const char *buffer;
    Py_ssize_t cbBuffer = 0;
    if (!entry->get || !entry->get(&buffer, &cbBuffer) || cbBuffer < _PYC_HEADER_LEN) {
        PyErr_Format(PyExc_ModuleNotFoundError, "unable to import '%s' %zi", entry->name, cbBuffer);
        return NULL;
    }
    if (PySys_Audit("pymsbuild.dllpack.load_pyc", "ss", _DLLPACK_NAME, entry->origin) < 0) {
        return NULL;
    }
    // Our .pyc has a header
    return PyMarshal_ReadObjectFromString(&buffer[_PYC_HEADER_LEN], cbBuffer - _PYC_HEADER_LEN);
}


static PyObject*
get_origin_root()
{
    Dl_info info = {0};
    if (!dladdr(&get_origin_root, &info)) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    const char *end = strrchr(info.dli_fname, '/');
    if (end) {
        Py_ssize_t len = end - info.dli_fname + 1;
        return PyUnicode_FromStringAndSize(info.dli_fname, len);
    } else if (info.dli_fname[0]) {
        return PyUnicode_FromFormat("%s/", info.dli_fname);
    } else {
        return PyUnicode_FromStringAndSize(NULL, 0);
    }
}


int
dllpack_exec_module(ModuleState *ms)
{
    return 0;
}

void
dllpack_free_module(ModuleState *ms)
{ }

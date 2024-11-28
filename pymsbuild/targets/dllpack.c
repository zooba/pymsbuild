#include "Python.h"
#include "marshal.h"

#include "dllpack.h"

#define MATCH_NONE 0
#define MATCH_FULL 1
#define MATCH_FULL_PACKAGE 2
#define MATCH_PARENT 3
#define MATCH_PREFIX 4

static int
entry_matches(const struct ENTRY *entry, const char *name, size_t cchName)
{
    if (!cchName) {
        cchName = strlen(name);
    }
    if (!cchName) {
        if (strchr(entry->name, '.')) {
            return MATCH_PARENT;
        }
        return MATCH_NONE;
    }

    if (!strcmp(entry->name, name)) {
        // Full name match
        if (entry->is_package) {
            return MATCH_FULL_PACKAGE;
        }
        return MATCH_FULL;
    }
    if (strncmp(entry->name, name, cchName) || entry->name[cchName] != '.') {
        return MATCH_NONE;
    }
    // Prefix match
    if (!strchr(&entry->name[cchName + 1], '.')) {
        // name is direct parent of this entry
        return MATCH_PARENT;
    }
    return MATCH_PREFIX;
}

static const struct ENTRY *
lookup_import(const char *name, int *is_package)
{
    int cchName = strlen(name);
    *is_package = 0;
    if (PySys_Audit("pymsbuild.dllpack.lookup_import", "ss", _DLLPACK_NAME, name) < 0) {
        return NULL;
    }
    for (struct ENTRY *entry = IMPORT_TABLE; entry->name; ++entry) {
        switch (entry_matches(entry, name, cchName)) {
        case MATCH_FULL:
            *is_package = 0;
            return entry;
        case MATCH_FULL_PACKAGE:
            *is_package = 1;
            return entry;
        case MATCH_PARENT:
        case MATCH_PREFIX:
            *is_package = 1;
            return NULL;
        }
    }
    return NULL;
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


static PyObject *
mod_exec_module_impl(ModuleState *ms, const char *name, PyObject *mod, int is_main) {
    int is_package = 0;
    const struct ENTRY *e = lookup_import(name, &is_package);
    if (!e && !is_package) {
        PyErr_Format(PyExc_ModuleNotFoundError, "'%s' is not part of this package", name);
        return NULL;
    }

    PyObject *pyc, *r;
    if (is_main) {
        pyc = load_pyc(ms, &_IMPORTERS);
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

    if (!e && is_package) {
        return mod;
    }

    pyc = load_pyc(ms, e);
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
mod_exec_module(PyObject *self, PyObject *args)
{
    PyObject *mod = NULL;
    if (!PyArg_ParseTuple(args, "O", &mod)) {
        return NULL;
    }
    mod = mod_exec_module_impl((ModuleState*)PyModule_GetState(self), PyModule_GetName(mod), mod, 0);
    Py_XINCREF(mod);
    return mod;
}


static PyObject *
mod_create_module(PyObject *self, PyObject *args)
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
    PyObject *loader, *path_prefix;
    PyObject *ilib_m = NULL, *mspec = NULL, *kwargs = NULL, *origin = NULL, *r = NULL;
    PyObject *args2 = NULL;

    if (!PyArg_ParseTuple(args, "sOO", &name, &loader, &path_prefix)) {
        return NULL;
    }

    if (PySys_Audit("pymsbuild.dllpack.makespec", "ssO", _DLLPACK_NAME, name, loader) < 0) {
        goto error;
    }

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
        if (!is_package) {
            e = lookup_redirect(name);
            if (!e) {
                if (!PyErr_Occurred()) {
                    r = Py_None;
                    Py_INCREF(r);
                }
                goto error;
            }
            Py_SETREF(loader, Py_None);
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
        if (e) {
            Py_SETREF(origin, PyUnicode_FromFormat("%U%s", origin, e->origin));
        } else {
            Py_SETREF(origin, PyUnicode_FromFormat("%U%s", origin, name));
        }
    }
    if (!origin) {
        goto error;
    }
    if (PyDict_SetItemString(kwargs, "origin", origin) < 0) {
        goto error;
    }

    if (is_package && PyDict_SetItemString(kwargs, "is_package", Py_True) < 0) {
        goto error;
    }

    args2 = Py_BuildValue("sO", name, loader);
    if (!args2) {
        goto error;
    }

    r = PyObject_Call(mspec, args2, kwargs);

    if (is_package) {
        PyObject *paths = PyList_New(0);
        if (!paths) {
            Py_CLEAR(r);
            goto error;
        }
        if (PyObject_IsTrue(path_prefix) && PyList_Append(paths, path_prefix) < 0) {
            Py_DECREF(paths);
            Py_CLEAR(r);
            goto error;
        }
        if (PyObject_SetAttrString(r, "submodule_search_locations", paths) < 0) {
            Py_DECREF(paths);
            Py_CLEAR(r);
            goto error;
        }
        Py_DECREF(paths);
    }
error:
    Py_XDECREF(origin);
    Py_XDECREF(kwargs);
    Py_XDECREF(mspec);
    Py_XDECREF(ilib_m);
    Py_XDECREF(args2);

    return r;
}

static int
_mod_module_names_append(PyObject *list, struct ENTRY *entry, const char *prefix, size_t cchPrefix)
{
    if (entry->name[0] == '.') {
        return 0;
    }
    int cchName = strlen(entry->name);
    int is_package = entry_matches(entry, entry->name, cchName) == MATCH_FULL_PACKAGE;
    if (!cchPrefix) {
        cchPrefix = strlen(prefix);
    }
    if (cchPrefix) {
        cchPrefix += 1;
    }
    PyObject *o = Py_BuildValue("si", &entry->name[cchPrefix], is_package);
    int r = -1;
    if (o) {
        r = PyList_Append(list, o);
        Py_DECREF(o);
    }
    return r;
}


static PyObject *
mod_module_names(PyObject *self, PyObject *args)
{
    const char *prefix;
    if (!PyArg_ParseTuple(args, "s", &prefix)) {
        return NULL;
    }
    size_t cchPrefix = strlen(prefix);
    if (PySys_Audit("pymsbuild.dllpack.module_names", "ss", _DLLPACK_NAME, prefix) < 0) {
        return NULL;
    }
    PyObject *r = PyList_New(0);
    if (!r) {
        return NULL;
    }
    for (struct ENTRY *entry = IMPORT_TABLE; entry->name; ++entry) {
        switch (entry_matches(entry, prefix, cchPrefix)) {
        case MATCH_PARENT:
            if (_mod_module_names_append(r, entry, prefix, cchPrefix) < 0) {
                Py_DECREF(r);
                return NULL;
            }
            break;
        }
    }
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
        return load_bytes(ms, e);
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
mod_exec(PyObject *m)
{
    ModuleState *ms = (ModuleState *)PyModule_GetState(m);
    if (!ms)
        return -1;
    if (dllpack_exec_module(ms) < 0)
        return -1;
    return mod_exec_module_impl(ms, PyModule_GetName(m), m, 1) ? 0 : -1;
}


static void
mod_free(PyObject *m)
{
    ModuleState *ms = (ModuleState *)PyModule_GetState(m);
    if (ms)
        dllpack_free_module(ms);
}


static struct PyMethodDef mod_meth[] = {
    {"__NAME", mod_name, METH_NOARGS, NULL},
    {"__MAKESPEC", mod_makespec, METH_VARARGS, NULL},
    {"__DATA", mod_data, METH_VARARGS, NULL},
    {"__DATA_NAMES", mod_data_names, METH_NOARGS, NULL},
    {"__CREATE_MODULE", mod_create_module, METH_VARARGS, NULL},
    {"__EXEC_MODULE", mod_exec_module, METH_VARARGS, NULL},
    {"__MODULE_NAMES", mod_module_names, METH_VARARGS, NULL},
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

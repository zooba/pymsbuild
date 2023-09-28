#include "Python.h"
#include "marshal.h"

#include "dllpack.h"

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


static PyObject *
mod_load_impl(ModuleState *ms, const char *name, PyObject *mod, int is_main) {
    int is_package = 0;
    const struct ENTRY *e = lookup_import(name, &is_package);
    if (!e) {
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
    PyObject *ilib_m = NULL, *mspec = NULL, *kwargs = NULL, *origin = NULL, *r = NULL;

    if (!PyArg_ParseTuple(args, "sO", &name, &loader)) {
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
    if (dllpack_exec_module(m) < 0)
        return -1;
    return mod_load_impl(ms, PyModule_GetName(m), m, 1) ? 0 : -1;
}


static void
mod_free(PyObject *m)
{
    dllpack_free_module(m);
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
    modmodule.m_size = dllpack_module_size();
    return PyModuleDef_Init(&modmodule);
}

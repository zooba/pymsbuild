#include "Python.h"

static PyObject *
mod_roj(PyObject *unused, PyObject *args, PyObject **kwargs)
{
    Py_RETURN_NONE;
}

static PyMethodDef mod_methods[] = {
    {"roj", mod_roj, METH_VARARGS, PyDoc_STR("roj(a,b) -> None")},
    {NULL, NULL} /* sentinel */
};

PyDoc_STRVAR(module_doc,
"This is a template module just for instruction.");

static int
mod_exec(PyObject *m)
{
    return 0;
}

static struct PyModuleDef_Slot mod_slots[] = {
    {Py_mod_exec, mod_exec},
    {0, NULL},
};

static struct PyModuleDef modmodule = {
    PyModuleDef_HEAD_INIT,
    "mod",
    module_doc,
    0,
    mod_methods,
    mod_slots,
    NULL,
    NULL,
    NULL
};

PyMODINIT_FUNC
PyInit_mod(void)
{
    return PyModuleDef_Init(&modmodule);
}

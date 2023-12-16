#include "Python.h"

static PyObject *
real_roj(PyObject *unused, PyObject *args, PyObject **kwargs)
{
    Py_RETURN_NONE;
}

static PyMethodDef real_methods[] = {
    {"roj", (PyCFunction)real_roj, METH_VARARGS, PyDoc_STR("roj(a,b) -> None")},
    {NULL, NULL} /* sentinel */
};

PyDoc_STRVAR(module_doc,
"This is a template module just for instruction.");

static int
real_exec(PyObject *m)
{
    return 0;
}

static struct PyModuleDef_Slot real_slots[] = {
    {Py_mod_exec, real_exec},
    {0, NULL},
};

static struct PyModuleDef realmodule = {
    PyModuleDef_HEAD_INIT,
    "real",
    module_doc,
    0,
    real_methods,
    real_slots,
    NULL,
    NULL,
    NULL
};

PyMODINIT_FUNC
PyInit_real(void)
{
    return PyModuleDef_Init(&realmodule);
}

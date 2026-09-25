#include <Python.h>

int shared_value(void);

static PyObject *value(PyObject *self, PyObject *args) {
    return PyLong_FromLong(shared_value());
}

static PyMethodDef methods[] = {
    {"value", value, METH_NOARGS, NULL},
    {NULL, NULL, 0, NULL},
};

static PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "module1",
    NULL,
    -1,
    methods,
};

PyMODINIT_FUNC PyInit_module1(void) {
    return PyModule_Create(&module);
}

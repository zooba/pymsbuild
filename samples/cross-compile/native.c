#include <Python.h>

#define STRINGIFY_VALUE(value) #value
#define STRINGIFY(value) STRINGIFY_VALUE(value)

static PyObject *properties(PyObject *self, PyObject *args)
{
    return Py_BuildValue(
        "(sssss)",
        STRINGIFY(TARGET_PYTHON_VERSION),
        STRINGIFY(PYTHON_TAG),
        STRINGIFY(ABI_TAG),
        STRINGIFY(PLATFORM_TAG),
        STRINGIFY(CROSS_COMPILE)
    );
}

static PyMethodDef methods[] = {
    {"properties", properties, METH_NOARGS, NULL},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "_native",
    NULL,
    -1,
    methods,
};

PyMODINIT_FUNC PyInit__native(void)
{
    return PyModule_Create(&module);
}

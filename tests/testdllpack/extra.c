#include "Python.h"

PyObject *
myfunc(PyObject *module, PyObject *args, PyObject *kwargs)
{
    PyObject *msg = PyUnicode_FromFormat(
        "module = %S\nargs = %S\nkwargs = %S",
        module,
        args,
        kwargs ? kwargs : Py_None
    );
    if (!msg) {
        return NULL;
    }
    printf("%s\n", PyUnicode_AsUTF8(msg));
    Py_DECREF(msg);
    Py_RETURN_NONE;
}

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#define stringize(x) #x
#define init(x, y) const char *x = stringize(y);
init(entrypointModule, _ENTRYPOINT_MODULE)
init(entrypointFunction, _ENTRYPOINT_FUNCTION)

int wmain(int argc, wchar_t **argv)
{
    Py_Initialize();
    PyObject *mod = PyImport_ImportModule(entrypointModule);
    PyObject *r = mod ? PyObject_CallMethod(mod, entrypointFunction, NULL) : NULL;
    if (!r) {
        PyErr_Print();
        return 1;
    }
    Py_Finalize();
    return 0;
}

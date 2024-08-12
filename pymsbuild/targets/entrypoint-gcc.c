#define PY_SSIZE_T_CLEAN
#include <Python.h>

#define _GNU_SOURCE 1
#include <unistd.h>

#define PYTHONPATH_T const char *
#define PYTHONPATH_ENTRY(s) s
#include "entrypoint.h"

#define CHECK_STATUS(op) status = op; \
if (PyStatus_Exception(status)) { \
    Py_ExitStatusException(status); \
    return -1; \
}


int main(int argc, char **argv)
{
    PyStatus status;
    PyPreConfig preconfig;
    PyConfig config;
    const size_t maxPath = 32678;
    char executable[maxPath];
    char home[maxPath];
    char *progname;

    if (argv[0][0] == '/' || !getcwd(executable, maxPath)) {
        strcpy(executable, argv[0]);
    } else {
        if (executable[strlen(executable) -1] != '/') {
            strcat(executable, "/");
        }
        strcat(executable, argv[0]);
    }
    strcpy(home, executable);
    strcat(executable, ".donotexecute");
    progname = strrchr(home, '/');
    if (progname) {
        *progname++ = '\0';
    }

    PyPreConfig_InitIsolatedConfig(&preconfig);
#ifdef _ENTRYPOINT_UTF8MODE
    preconfig.utf8_mode = _ENTRYPOINT_UTF8MODE;
#endif

    CHECK_STATUS(Py_PreInitialize(&preconfig));
    PyConfig_InitIsolatedConfig(&config);
    CHECK_STATUS(PyConfig_SetBytesArgv(&config, argc, argv));
#if PY_HEXVERSION >= 0x030B0000
    config.code_debug_ranges = 0;
#endif
    config.configure_c_stdio = 1;
    PyConfig_SetBytesString(&config, &config.exec_prefix, home);
    PyConfig_SetBytesString(&config, &config.executable, executable);
    PyConfig_SetBytesString(&config, &config.home, home);
    PyConfig_SetBytesString(&config, &config.prefix, home);
    if (progname) {
        PyConfig_SetBytesString(&config, &config.program_name, progname);
    }
#ifdef _ENTRYPOINT_IMPORTTIME
    config.import_time = _ENTRYPOINT_IMPORTTIME;
#endif
    config.install_signal_handlers = 1;

    for (PYTHONPATH_T *p = entrypointPythonPath; *p; ++p) {
        char searchPath[maxPath];
        if (*p[0] == '/') {
            strcpy(searchPath, *p);
        } else if (strcmp(*p, ".")) {
            snprintf(searchPath, maxPath, "%s/%s", home, *p);
        } else {
            strcpy(searchPath, home);
        }
        const wchar_t *wpath = Py_DecodeLocale(searchPath, NULL);
        if (wpath) {
            CHECK_STATUS(PyWideStringList_Append(&config.module_search_paths, wpath));
            PyMem_RawFree((void *)wpath);
        } else {
            fprintf(stderr, "WARN: failed to add search path %s\n", *p);
        }
    }
    config.module_search_paths_set = 1;
    config.optimization_level = 2;
    config.site_import = 0;
#if PY_HEXVERSION >= 0x030C0000
    config.perf_profiling = 0;
#endif
    config.write_bytecode = 0;

    CHECK_STATUS(Py_InitializeFromConfig(&config));

    PyObject *mod = PyImport_ImportModule(entrypointModule);
    PyObject *r = mod ? PyObject_CallMethod(mod, entrypointFunction, NULL) : NULL;
    if (!r) {
        PyErr_Print();
        return 1;
    }
    Py_DECREF(r);
    Py_DECREF(mod);
    Py_Finalize();
    return 0;
}

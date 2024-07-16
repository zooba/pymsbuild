#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <windows.h>
#include <pathcch.h>
#pragma comment(lib, "pathcch.lib")

#define PYTHONPATH_T const wchar_t *
#define PYTHONPATH_ENTRY(s) L ## s
#include "entrypoint.h"

#define CHECK_STATUS(op) status = op; \
if (PyStatus_Exception(status)) { \
    Py_ExitStatusException(status); \
    return -1; \
}


int wmain(int argc, wchar_t **argv)
{
    PyStatus status;
    PyPreConfig preconfig;
    PyConfig config;
    const size_t maxPath = 32678;
    wchar_t executable[maxPath];
    wchar_t home[maxPath];
    wchar_t *progname;
    if (!GetModuleFileNameW(NULL, executable, maxPath) ||
        wcscpy_s(home, maxPath, executable) ||
        FAILED(PathCchRemoveFileSpec(home, maxPath))) {
        executable[0] = L'\0';
        home[0] = L'\0';
    }
    progname = &executable[wcslen(home)];
    if (executable[0]) {
        wcscat_s(executable, maxPath, L".donotexecute");
    }
    if (*progname == L'\\') ++progname;

    PyPreConfig_InitIsolatedConfig(&preconfig);
#ifdef _ENTRYPOINT_UTF8MODE
    preconfig.utf8_mode = _ENTRYPOINT_UTF8MODE;
#endif

    CHECK_STATUS(Py_PreInitialize(&preconfig));
    PyConfig_InitIsolatedConfig(&config);
    CHECK_STATUS(PyConfig_SetArgv(&config, argc, argv));
#if PY_HEXVERSION >= 0x030B0000
    config.code_debug_ranges = 0;
#endif
    config.configure_c_stdio = 1;
    PyConfig_SetString(&config, &config.exec_prefix, home);
    PyConfig_SetString(&config, &config.executable, executable);
    PyConfig_SetString(&config, &config.home, home);
    PyConfig_SetString(&config, &config.prefix, home);
    PyConfig_SetString(&config, &config.program_name, progname);
#ifdef _ENTRYPOINT_IMPORTTIME
    config.import_time = _ENTRYPOINT_IMPORTTIME;
#endif
    config.install_signal_handlers = 1;

    for (PYTHONPATH_T *p = entrypointPythonPath; *p; ++p) {
        wchar_t searchPath[maxPath];
        searchPath[0] = L'\0';
        if (FAILED(PathCchCombineEx(searchPath, maxPath, home, *p, PATHCCH_ALLOW_LONG_PATHS))) {
            fprintf(stderr, "WARN: failed to add search path %S\n", *p);
        } else {
            CHECK_STATUS(PyWideStringList_Append(&config.module_search_paths, searchPath));
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
    PyObject *r;
    if (entrypointFunction && entrypointFunction[0]) {
        r = mod ? PyObject_CallMethod(mod, entrypointFunction, NULL) : NULL;
    } else {
        r = mod ? Py_None : NULL;
        Py_XINCREF(r);
    }
    if (!r) {
        PyErr_Print();
        return 1;
    }
    Py_DECREF(r);
    Py_DECREF(mod);
    Py_Finalize();
    return 0;
}

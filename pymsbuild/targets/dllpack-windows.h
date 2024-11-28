#include <windows.h>
#include "Python.h"
#include "marshal.h"


#define STATUS_DATA_ERROR 0xC000003E

#ifdef _ENCRYPT_KEY_NAME
static const wchar_t *encrypt_variable = _ENCRYPT_KEY_NAME;
#else
static const wchar_t *encrypt_variable = NULL;
#endif

struct ENTRY {
    const char *name;
    const char *origin;
    int id;
    char is_package;
};


static HMODULE hInstance;

typedef struct {
    BCRYPT_ALG_HANDLE hAlg;
    BCRYPT_KEY_HANDLE hKey;
} ModuleState;


static void *
decrypt_buffer(ModuleState *ms, const char **buffer, DWORD *cbBuffer)
{
    struct hdr {
        DWORD cbPlain;
        DWORD cbData;
        DWORD cbIV;
        const UCHAR iv[512];
    } *header = (struct hdr*)*buffer;
    UCHAR iv[512];
    if (PySys_Audit("pymsbuild.dllpack.decrypt_buffer", "III", header->cbData, header->cbPlain, header->cbIV) < 0) {
        return NULL;
    }
    if (header->cbIV > sizeof(iv)) {
        PyErr_Format(PyExc_OverflowError, "requested IV length (%i) is too large", header->cbIV);
        return NULL;
    }
    memcpy(iv, header->iv, header->cbIV);
    PUCHAR data = (PUCHAR)&header->iv[header->cbIV];
    DWORD cbPlainActual;
    PUCHAR plain = (PUCHAR)HeapAlloc(GetProcessHeap(), HEAP_GENERATE_EXCEPTIONS, header->cbPlain);

    NTSTATUS err = BCryptDecrypt(
        ms->hKey,
        data, header->cbData,
        NULL,
        iv, header->cbIV,
        plain, header->cbPlain,
        &cbPlainActual,
        BCRYPT_BLOCK_PADDING
    );
    if (err) {
        HeapFree(GetProcessHeap(), 0, plain);
        if (err == STATUS_DATA_ERROR) {
            PyErr_SetString(PyExc_ImportError, "Failed to decode module");
        } else {
            PyErr_SetFromWindowsErr(err);
        }
        return NULL;
    }

    *buffer = (const char *)plain;
    *cbBuffer = cbPlainActual;
    return plain;
}

static void
free_decrypt_cookie(void *cookie)
{
    HeapFree(GetProcessHeap(), 0, cookie);
}


static PyObject *
load_bytes(ModuleState *ms, const struct ENTRY *entry)
{
    if (!entry->id) {
        PyErr_Format(PyExc_ModuleNotFoundError, "unable to open '%s'", entry->origin);
        return NULL;
    }
    if (PySys_Audit("pymsbuild.dllpack.load_bytes", "ss", _DLLPACK_NAME, entry->origin) < 0) {
        return NULL;
    }
    PyObject *obj;
    HRSRC block = FindResourceW(hInstance, MAKEINTRESOURCE(entry->id), MAKEINTRESOURCE(_DATAFILE));
    if (!block) {
        PyErr_SetFromWindowsErr(GetLastError());
        return NULL;
    }
    DWORD cbBuffer = SizeofResource(hInstance, block);
    if (!cbBuffer) {
        PyErr_SetFromWindowsErr(GetLastError());
        return NULL;
    }
    HGLOBAL res = LoadResource(hInstance, block);
    if (!res) {
        PyErr_SetFromWindowsErr(GetLastError());
        return NULL;
    }
    const char *buffer = (const char*)LockResource(res);
    if (!buffer) {
        PyErr_SetFromWindowsErr(GetLastError());
        FreeResource(res);
        return NULL;
    }
    void *decrypt_cookie = NULL;
    if (encrypt_variable) {
        decrypt_cookie = decrypt_buffer(ms, &buffer, &cbBuffer);
        if (!decrypt_cookie) {
            FreeResource(res);
            return NULL;
        }
    }
    obj = PyBytes_FromStringAndSize(buffer, cbBuffer);
    FreeResource(res);
    free_decrypt_cookie(decrypt_cookie);
    return obj;
}

static PyObject *
load_pyc(ModuleState *ms, const struct ENTRY *entry)
{
    if (!entry->id) {
        PyErr_Format(PyExc_ModuleNotFoundError, "unable to import '%s'", entry->name);
        return NULL;
    }
    if (PySys_Audit("pymsbuild.dllpack.load_pyc", "ss", _DLLPACK_NAME, entry->origin) < 0) {
        return NULL;
    }
    PyObject *obj;
    HRSRC block = FindResourceW(hInstance, MAKEINTRESOURCE(entry->id), MAKEINTRESOURCE(_PYCFILE));
    if (!block) {
        PyErr_SetFromWindowsErr(GetLastError());
        return NULL;
    }
    DWORD cbBuffer = SizeofResource(hInstance, block);
    if (!cbBuffer) {
        PyErr_SetFromWindowsErr(GetLastError());
        return NULL;
    }
    HGLOBAL res = LoadResource(hInstance, block);
    if (!res) {
        PyErr_SetFromWindowsErr(GetLastError());
        return NULL;
    }
    const char *buffer = (const char*)LockResource(res);
    if (!buffer) {
        PyErr_SetFromWindowsErr(GetLastError());
        FreeResource(res);
        return NULL;
    }
    void *decrypt_cookie = NULL;
    if (encrypt_variable) {
        decrypt_cookie = decrypt_buffer(ms, &buffer, &cbBuffer);
        if (!decrypt_cookie) {
            FreeResource(res);
            return NULL;
        }
    }
    // Our .pyc has a header
    obj = PyMarshal_ReadObjectFromString(&buffer[_PYC_HEADER_LEN], cbBuffer - _PYC_HEADER_LEN);
    FreeResource(res);
    free_decrypt_cookie(decrypt_cookie);
    return obj;
}

static PyObject*
get_origin_root()
{
    wchar_t buff[256];
    DWORD cch = GetModuleFileNameW(hInstance, buff, sizeof(buff) / sizeof(buff[0]));
    if (cch == 0) {
        PyErr_SetFromWindowsErr(GetLastError());
        return NULL;
    } else if (cch < sizeof(buff) / sizeof(buff[0])) {
        while (cch && buff[cch - 1] != '\\' && buff[cch - 1] != '/') {
            --cch;
        }
        return PyUnicode_FromWideChar(buff, cch);
    }
    cch += 1;
    wchar_t *buff2 = (wchar_t *)PyMem_Malloc(sizeof(wchar_t) * cch);
    if (!buff2) {
        return NULL;
    }
    DWORD cch2 = GetModuleFileNameW(hInstance, buff2, cch);
    PyObject *r = NULL;
    if (cch2 == 0) {
        PyErr_SetFromWindowsErr(GetLastError());
    } else if (cch2 >= cch) {
        PyErr_SetString(PyExc_SystemError, "failed to get DLL name; cannot import");
    } else {
        while (cch2 & buff2[cch2 - 1] != '\\' && buff2[cch2 - 1] != '/') {
            --cch2;
        }
        r = PyUnicode_FromWideChar(buff2, cch2);
    }
    PyMem_Free(buff2);
    return r;
}


static int
init_decryptor(ModuleState *ms)
{
    char key[4096];
    DWORD cbKey = sizeof(key);
    wchar_t buffer[4096];
    NTSTATUS err;

    ms->hAlg = NULL;
    ms->hKey = NULL;

    if (GetEnvironmentVariableW(encrypt_variable, buffer, 4096) == 0) {
        PyErr_SetFromWindowsErr(GetLastError());
        return -1;
    }
    SetEnvironmentVariableW(encrypt_variable, NULL);
    if (0 == wcsncmp(buffer, L"base64:", 7)) {
        if (!CryptStringToBinaryW(&buffer[7], 0, CRYPT_STRING_BASE64, key, &cbKey, NULL, NULL)) {
            PyErr_SetFromWindowsErr(GetLastError());
            return -1;
        }
    } else {
        cbKey = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, buffer, -1, key, cbKey, NULL, NULL);
        if (!cbKey) {
            PyErr_SetFromWindowsErr(GetLastError());
            return -1;
        }
        cbKey -= 1;
    }

    err = BCryptOpenAlgorithmProvider(&ms->hAlg, BCRYPT_AES_ALGORITHM, NULL, 0);
    if (!err) {
        err = BCryptSetProperty(
            ms->hAlg,
            BCRYPT_CHAINING_MODE,
            (PUCHAR)BCRYPT_CHAIN_MODE_CBC,
            -1,
            0
        );
    }
    if (!err) {
        err = BCryptGenerateSymmetricKey(ms->hAlg, &ms->hKey, NULL, 0, key, cbKey, 0);
    }
    if (err) {
        PyErr_SetFromWindowsErr(err);
        return -1;
    }
    return 0;
}


static int
free_decryptor(ModuleState *ms)
{
    if (ms->hKey) {
        BCryptDestroyKey(ms->hKey);
        ms->hKey = NULL;
    }
    if (ms->hAlg) {
        BCryptCloseAlgorithmProvider(ms->hAlg, 0);
        ms->hAlg = NULL;
    }
    return 0;
}


int
dllpack_exec_module(ModuleState *ms)
{
    if (!encrypt_variable) {
        return 0;
    }

    if (init_decryptor(ms) < 0) {
        free_decryptor(ms);
        return -1;
    }

    return 0;
}


void
dllpack_free_module(ModuleState *ms)
{
    free_decryptor(ms);
}


BOOL WINAPI
DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpReserved)
{
    switch( fdwReason )
    {
        case DLL_PROCESS_ATTACH:
            hInstance = hinstDLL;
            break;
        case DLL_THREAD_ATTACH:
            break;
        case DLL_THREAD_DETACH:
            break;
        case DLL_PROCESS_DETACH:
            break;
    }
    return TRUE;
}

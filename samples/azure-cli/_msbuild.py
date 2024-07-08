import os
from pathlib import Path
from pymsbuild import *
from pymsbuild.dllpack import DllPackage, PydRedirect
from pymsbuild.entrypoint import Entrypoint, SearchPath

METADATA = {
    "Metadata-Version": "2.1",
    "Name": "azure-cli",
    "Version": "1.0",
    "Author": "Steve Dower",
    "Author-email": "steve.dower@microsoft.com",
    "Home-page": "https://github.com/zooba/pymsbuild",
    "Project-url": [
        "Bug Tracker, https://github.com/zooba/pymsbuild/issues",
    ],
    "Summary": "A sample of packing the Azure CLI",
}

PACKAGES = [
    "adal",
    "adodbapi",
    "antlr4",
    "applicationinsights",
    "argcomplete",
    "azure",
    "bcrypt",
    "certifi",
    "cffi",
    "chardet",
    "charset_normalizer",
    "colorama",
    "cryptography",
    "dateutil",
    "deprecated",
    "fabric",
    "github",
    "humanfriendly",
    "idna",
    "invoke",
    "isapi",
    "isodate",
    "javaproperties",
    "jmespath",
    "jsondiff",
    "jwt",
    "knack",
    "msal",
    "msal_extensions",
    "msrest",
    "msrestazure",
    "nacl",
    "oauthlib",
    "OpenSSL",
    "packaging",
    "paramiko",
    "pip",
    "pkginfo",
    "portalocker",
    "psutil",
    "pycomposefile",
    "pycparser",
    "pygments",
    "pymsalruntime",
    "pyreadline3",
    "pythonwin",
    "requests",
    "requests_oauthlib",
    "samples",
    "tabulate",
    "tests",
    "urllib3",
    "websocket",
    "wrapt",
    "yaml",
    "_yaml",
]

class SiteFile(File):
    options = {"IncludeInSdist": False}

class SiteModule(File):
    options = {"IncludeInSdist": False }


PACKAGE = Package("azure-cli",
    SourceFile("requirements.txt"),
    *[DllPackage(p) for p in PACKAGES],
    SiteFile("*.py"),
    SiteModule("_cffi_backend"),
    SiteFile("pywin32_system32/*.dll"),
    SiteFile("win32/*.pyd"),
    SiteFile("win32/lib/*.py"),
    Package("setuptools", SiteFile("setuptools/**/*.py")),
    Package("_distutils_hack", SiteFile("_distutils_hack/**/*.py")),
    Entrypoint(
        "az", "azure.cli", "main",
        VersionInfo(
            LegalCopyright="Copyright Me",
        ),
        #Icon("Globe1.ico"),
        SearchPath("."),
        SearchPath("stdlib.zip"),
    ),
)


def init_METADATA():
    import os, re
    _, sep, version = os.getenv("GITHUB_REF", "").rpartition("/")
    if sep and re.match(r"(\d+!)?\d+(\.\d+)+((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?$", version):
        # Looks like a version tag
        METADATA["Version"] = version

    with open("requirements.txt", "r", encoding="utf-8") as f:
        METADATA["BuildWheelRequires"] = list(map(str.strip, f))


def find_spec(name):
    from importlib.util import find_spec
    spec = find_spec(str(name))
    if not spec:
        raise RuntimeError(f"Cannot find {name!r}. Ensure it is listed in requirements.txt")
    return spec


def init_PACKAGE(tag=None):
    if not tag:
        return

    spec = find_spec("six")
    site = Path(spec.origin).parent
    queue = PACKAGE.members[:]
    while queue:
        m = queue.pop(0)
        if isinstance(m, SiteFile):
            m.source = site / m.source
        elif isinstance(m, SiteModule):
            spec = find_spec(m.source)
            m.source = spec.origin
            m.name = Path(spec.origin).name
        elif isinstance(m, Package):
            queue.extend(m.members)

    for p in PACKAGES:
        if p == 'distutils':
            spec = find_spec('setuptools._distutils')
        else:
            spec = find_spec(p)
        v = PACKAGE.find(p)
        if not spec.submodule_search_locations:
            raise ValueError(spec)
        for src in spec.submodule_search_locations:
            if v.source:
                v.members.append(PyFile(Path(src) / "**/*.py", allow_none=True, IncludeInSdist=False))
            else:
                v.source = src
                v.members.append(PyFile("**/*.py", allow_none=True, IncludeInSdist=False))

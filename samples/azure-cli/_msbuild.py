import os
import re
import sys
from importlib.util import find_spec
from pathlib import Path, PurePath
from pymsbuild import *
from pymsbuild.dllpack import DllPackage, PydRedirect
from pymsbuild.entrypoint import *
from pymsbuild.vendor import *

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


with open(f"requirements-{sys.platform}.txt", "r", encoding="utf-8") as f:
    METADATA["BuildWheelRequires"] = [s for s in (s.strip() for s in f) if s[:1] not in ('#', '')]


def spec_name(spec):
    return re.sub(r'[^a-z0-9]', '_', re.match(r'([a-z0-9.\-_]+)', spec.lower()).groups()[0])


PACKAGE_SPECS = {spec_name(s): s for s in METADATA["BuildWheelRequires"] if not s.startswith("azure-")}

# Packages where the package name doesn't match the import name.
NAME_FIXUPS = {
    "antlr4_python3_runtime": "antlr4",
    "pygithub": "github",
    "pyjwt": "jwt",
    "pynacl": "nacl",
    "pyopenssl": "OpenSSL",
    "pysocks": "socks",
    "python_dateutil": "dateutil",
    "pyyaml": "yaml",
    "websocket_client": "websocket",
}

for n in NAME_FIXUPS:
    assert n in PACKAGE_SPECS, n

PACKAGES = {
    **{n: VendoredDllPackage(s, NAME_FIXUPS.get(n)) for n, s in PACKAGE_SPECS.items()},

    # Override some packages that won't work as DLLs
    "setuptools": VendoredPackage(PACKAGE_SPECS["setuptools"]),
    "_distutils_hack": VendoredPackage(PACKAGE_SPECS["setuptools"], "_distutils_hack"),
    "pkg_resources": VendoredPackage(PACKAGE_SPECS["setuptools"], "pkg_resources"),
    "_cffi_backend": File("_cffi_backend", IncludeInSdist=False),
}


if "pywin32" in PACKAGES:
    # pywin32 is so messy we just put it all in its own search path
    PACKAGES["pywin32"] = VendoredPackage(PACKAGE_SPECS["pywin32"], as_search_path=True)
    # We won't get pywin32.pth automatically, so add its paths instead
    # We also add its 'import pywin32_bootstrap' to our main.py
    PYWIN32_SEARCH_PATHS = [
        SearchPath("vendored/pywin32"),
        SearchPath("vendored/pywin32/pythonwin"),
        SearchPath("vendored/pywin32/win32"),
        SearchPath("vendored/pywin32/win32/lib"),
    ]
else:
    PYWIN32_SEARCH_PATHS = []


class SiteFile(File):
    def _match(self, key):
        if key == "$SITEFILE":
            return True
        return PurePath(self.name).match(key)


PACKAGE = Package(
    "azure-cli",
    SourceFile("requirements-win32.txt"),
    SourceFile("requirements-linux.txt"),

    Package("azure"),

    # Put all vendored packages in their own directory, and add a search path below
    Package("vendored", *[p for p in PACKAGES.values() if p]),

    PyFile("main.py"),
    Entrypoint(
        "az", "main", "run",
        VersionInfo(
            LegalCopyright="Copyright Microsoft",
        ),
        #Icon("Globe1.ico"),
        SearchPath("."),
        SearchPath("vendored"),
        DefaultSearchPath(),
        *PYWIN32_SEARCH_PATHS
    ),
)


def init_METADATA():
    import os, re
    _, sep, version = os.getenv("GITHUB_REF", "").rpartition("/")
    if sep and re.match(r"(\d+!)?\d+(\.\d+)+((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?$", version):
        # Looks like a version tag
        METADATA["Version"] = version


def init_PACKAGE(tag=None):
    if not tag:
        return

    VendoredPackage.collect_all(PACKAGE, tag)

    spec = find_spec("_cffi_backend")
    PACKAGES["_cffi_backend"].source = spec.origin
    PACKAGES["_cffi_backend"].name = Path(spec.origin).name

    azure = PACKAGE.find("azure")
    import azure as azure_module
    azure_paths = [Path(p) / n for p in azure_module.__path__ for n in os.listdir(p)]
    for p in azure_paths:
        azure.members.append(
            DllPackage(
                p.name,
                PyFile(p / "**/*.py"),
                RootNamespace=f"azure.{p.name}",
            )
        )

import os
from pathlib import Path
from pymsbuild import *
from pymsbuild.dllpack import DllPackage, PydRedirect

METADATA = {
    "Metadata-Version": "2.1",
    "Name": "azure-pack",
    "Version": "1.0",
    "Author": "Steve Dower",
    "Author-email": "steve.dower@python.org",
    "Home-page": "https://github.com/zooba/pymsbuild",
    "Project-url": [
        "Bug Tracker, https://github.com/zooba/pymsbuild/issues",
    ],
    "Summary": "A sample of packing some Azure libraries into .pyds",
}

# These packages will be collected from all *.py files in their
# installed locations.
AUTO_PACKAGES = [
    "charset_normalizer",
    "cryptography",
    "idna",
    "isodate",
    "msal",
    "requests",
    "six",
    "typing_extensions",
    "urllib3",
]

# These packages will also have all *.py files collected, but may have
# additional files or options applied.
PACKAGES = {
    "azure": DllPackage(
        "azure",
        PyFile(name="__init__.py", source=Path("empty.py").absolute()),
        PyFile(name="storage/__init__.py", source=Path("empty.py").absolute()),
    ),
    "certifi": DllPackage("certifi", File("**/*.pem", IncludeInSdist=False, allow_none=True)),
    "cffi_backend": File("empty.py", name="_cffi_backend.pyd", IncludeInSdist=False),
    **{k: DllPackage(k) for k in AUTO_PACKAGES}
}


PACKAGE = Package("azure-pack",
    SourceFile("requirements-win32.txt"),
    File("azure-pack.pth.in", name="../azure-pack.pth", IncludeInLayout=False),
    *PACKAGES.values(),
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
    spec = find_spec(name)
    if not spec:
        raise RuntimeError(f"Cannot find {name!r}. Ensure it is listed in requirements.txt")
    return spec


def init_PACKAGE(tag=None):
    if not tag:
        return

    for k, v in PACKAGES.items():
        if isinstance(v, DllPackage):
            spec = find_spec(v.name)
            if spec.submodule_search_locations:
                v.source = spec.submodule_search_locations[0]
                v.members.append(PyFile("**/*.py"))
                v.members.append(PydRedirect("**/*.pyd", allow_none=True))
            else:
                v.members.append(PyFile(name="__init__.py", source=Path(spec.origin)))

    PACKAGE.find("_cffi_backend.pyd").source = find_spec("_cffi_backend").origin

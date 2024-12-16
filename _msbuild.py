import os
from pymsbuild import *

METADATA = {
    "Metadata-Version": "2.2",
    "Name": "pymsbuild",
    "Version": "0.0.1",
    "Author": "Steve Dower",
    "Author-email": "steve.dower@python.org",
    "Project-url": [
        "Homepage, https://github.com/zooba/pymsbuild",
        "Source, https://github.com/zooba/pymsbuild",
        "Issues, https://github.com/zooba/pymsbuild/issues",
    ],
    "Summary": "The pymsbuild build backend.",
    "Description": File("README.md"),
    "Description-Content-Type": "text/markdown",
    "Keywords": "build,pep-517,msbuild,packaging,cython",
    "Classifier": [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Compilers",
        "Topic :: Utilities",
    ],
    "Requires-External": "msbuild,dotnet",
    "Requires-Dist": [
        "packaging",
    ],
    "WheelTag": "py3-none-any",
}

PACKAGE = Package(
    "pymsbuild",
    PyFile("pymsbuild/*.py").excluding("pymsbuild/__init__.py"),
    PyFile("pymsbuild/__init__.py", IncludeInWheel=False),
    PyFile("pymsbuild/__init__.py.ver", name="__init__.py"),
    File("pymsbuild/*.in"),
    File("pymsbuild/targets/*", name="targets/*"),
)

def init_METADATA():
    version = os.getenv("BUILD_BUILDNUMBER")
    ghref = os.getenv("GITHUB_REF")
    if ghref:
        version = ghref.rpartition("/")[2]
    if version:
        METADATA["Version"] = version

def init_PACKAGE(tag=None):
    if not os.path.exists("pymsbuild/__init__.py.ver"):
        with open("pymsbuild/__init__.py", "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("%VERSION%", METADATA["Version"])
        with open("pymsbuild/__init__.py.ver", "w", encoding="utf-8") as f:
            f.write(content)

import os
from pymsbuild import *

METADATA = {
    "Metadata-Version": "2.1",
    "Name": "pymsbuild",
    "Version": os.getenv("BUILD_BUILDNUMBER", "0.0.16"),
    "Author": "Steve Dower",
    "Author-email": "Steve Dower <steve.dower@python.org>",
    "Home-page": "https://github.com/zooba/pymsbuild",
    "Project-url": [
        "Bug Tracker, https://github.com/zooba/pymsbuild/issues",
    ],
    "Summary": "The pymsbuild build backend.",
    "Description": File("README.md"),
    "Description-Content-Type": "text/markdown",
    "Keywords": "build,pep-517,msbuild,packaging",
    "Classifier": [
        "Development Status :: 3 - Alpha",
        "Environment :: Win32 (MS Windows)",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Compilers",
        "Topic :: Utilities",
    ],
    "Requires-Python": ">=3.7",
    "Requires-External": "msbuild",
    "Requires-Dist": [
        "packaging",
    ],
    "WheelTag": "py3-none-any",
}

PACKAGE = Package(
    "pymsbuild",
    PyFile("pymsbuild\\*.py"),
    File("pymsbuild\\targets\\*", name="targets\\*"),
)

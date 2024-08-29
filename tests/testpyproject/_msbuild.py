from pymsbuild import *

METADATA = {
    "Name": "testpyproject",
    "Version": "0.0.1",
    "Summary": "A test project",
    "Description": """The documentation for my test project.

With multiple lines.""",
    "Description-Content-Type": "text/plain",
    "Keywords": "test,project",
    "Classifier": [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
    ],
}

PACKAGE = Package(
    "testpyproject",
    SourceFile("pyproject.toml"),
)

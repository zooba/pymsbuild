from pymsbuild import *

SHARED = CProject(
    "shared",
    CSourceFile("shared.c"),
    ConfigurationType="StaticLibrary",
)

PACKAGE = Package(
    "testnative",
    PydFile("module1", SHARED, CSourceFile("module1.c")),
    PydFile("module2", SHARED, CSourceFile("module2.c")),
)

METADATA = {
    "Name": "testnative",
    "Version": "1.0.0",
}

def init_PACKAGE(tag=None):
    generated = get_current_build_state().temp_dir / "generated.h"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text("/* generated */\n", encoding="utf-8")
    SHARED.members.append(IncludeFile(generated, name="generated.h"))

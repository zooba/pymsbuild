import os
import pathlib
import pytest
import subprocess
import sys

PYMSBUILD_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PYMSBUILD_ROOT)

from pymsbuild._build import locate_msbuild

# Avoid calling locate() for each test
if not os.getenv("MSBUILD"):
    os.environ["MSBUILD"] = " ".join(locate_msbuild())
    if os.environ["MSBUILD"] != " ".join(locate_msbuild()):
        # We can't avoid it for some reason...
        del os.environ["MSBUILD"]


def run_build(cwd, tmp_path, config=None, env=None):
    root = tmp_path / "build"
    layout = tmp_path / "layout"
    env = {
        **os.environ,
        "PYMSBUILD_FORCE": "1",
        "PYMSBUILD_VERBOSE": "1",
        "PYMSBUILD_TEMP_DIR": str(root),
        "_PYMSBUILD_SOURCE_LAYOUT_DIR": str(layout),
        "PYTHONPATH": PYMSBUILD_ROOT,
        **(env if env else {}),
    }
    if config:
        env["PYMSBUILD_CONFIG"] = str(config)

    subprocess.check_call(
        [sys.executable, "-m", "pymsbuild"],
        env=env,
        cwd=str(cwd),
    )
    built = [p.relative_to(layout) for p in layout.rglob("*") if p.is_file()]
    print("Files:")
    print(*(f" * {p}" for p in built), sep="\n")
    return built


@pytest.mark.parametrize("configuration", ["Debug", "Release"])
@pytest.mark.skipif(sys.platform not in {"win32"}, reason="Only supported on Windows")
def test_entry(testdata, tmp_path, configuration):
    built = run_build(
        testdata / "testentry",
        tmp_path,
        env={
            "PYMSBUILD_CONFIGURATION": configuration,
        },
    )
    assert pathlib.Path("testentry/run.exe") in built, "did not find run.exe"
    assert any(p.match("testentry/python3*.dll") for p in built), "did not find python3*.dll"
    assert any(p.match("testentry/files/app.*.pyd") for p in built), "did not find app.*.pyd"

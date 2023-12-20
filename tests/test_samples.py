import importlib.machinery
import os
import pytest
import shutil
import subprocess
import sys

from pathlib import Path

ROOT = Path(__file__).absolute().parent.parent

ENV = {
    **os.environ,
    "PYTHONPATH": str(ROOT),
    "PYTHONHOME": "",
    "PIP_DISABLE_PIP_VERSION_CHECK": "true",
    "PIP_NO_COLOR": "true",
    "PIP_NO_INPUT": "true",
    "PIP_PROGRESS_BAR": "off",
    "PIP_REQUIRE_VIRTUALENV": "false",
    "PIP_VERBOSE": "true",
    "PYMSBUILD_VERBOSE": "true",
}

WIN32_SAMPLES = {
    "azure-pack",
}


POSIX_SAMPLES = set()

def all_samples(f):
    return pytest.mark.parametrize(
        "sample", 
        sorted(WIN32_SAMPLES | POSIX_SAMPLES)
    )(f)


def maybe_skip(sample):
    if sys.platform == "win32" and sample not in WIN32_SAMPLES:
        pytest.skip("not a Windows sample")
    elif sys.platform != "win32" and sample not in POSIX_SAMPLES:
        pytest.skip("Windows-only sample")


def fresh_copy(sample, tmp_path):
    DIR = ROOT / "samples" / sample
    TMP = tmp_path / sample
    shutil.copytree(DIR, TMP)
    return TMP


def rglob_ext(root):
    root = Path(root)
    exts = set()
    for suffix in importlib.machinery.EXTENSION_SUFFIXES:
        exts.update(root.rglob(f"*{suffix}"))
    return exts


@all_samples
def test_sample_build_inplace(sample, tmp_path):
    maybe_skip(sample)
    DIR = fresh_copy(sample, tmp_path)
    orig_files = {f.relative_to(DIR) for f in DIR.rglob("*")}
    env = dict(ENV)

    if (DIR / "requirements.txt").is_file():
        PACKAGES = tmp_path / "packages"
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", DIR / "requirements.txt", "--target", PACKAGES],
            env=env,
        )
        env["PYTHONPATH"] = os.pathsep.join(str(s) for s in [PACKAGES, env["PYTHONPATH"]] if s)

    subprocess.check_call(
        [sys.executable, "-m", "pymsbuild"],
        cwd=DIR,
        env=env,
    )
    modules = {f.relative_to(DIR) for f in rglob_ext(DIR)}
    without_temp = {f for f in modules if f.parts[0] != "build"}
    assert without_temp

    env["BUILD_PREFIX"] = str(DIR)
    env["PYTHONPATH"] = ""
    subprocess.check_call(
        [sys.executable, DIR / "tests/test-sample.py"],
        cwd=DIR,
        env=env,
    )

@all_samples
def test_sample_sdist(sample, tmp_path):
    maybe_skip(sample)
    DIR = ROOT / "samples" / sample
    OUT = tmp_path / "out"
    subprocess.check_call(
        [sys.executable, "-m", "pymsbuild", "sdist", "-d", OUT],
        cwd=DIR,
        env=ENV,
    )
    dist = set(OUT.glob("*.tar.gz"))
    assert dist

@all_samples
def test_sample_build_sdist(sample, tmp_path):
    maybe_skip(sample)
    DIR = ROOT / "samples" / sample
    OUT = tmp_path / "out"
    subprocess.check_call(
        [sys.executable, "-m", "build", "--sdist", "-o", OUT],
        cwd=DIR,
        env=ENV,
    )
    dist = set(OUT.glob("*.tar.gz"))
    assert dist

@all_samples
def test_sample_build_wheel(sample, tmp_path):
    maybe_skip(sample)
    DIR = ROOT / "samples" / sample
    OUT = tmp_path / "out"
    subprocess.check_call(
        [sys.executable, "-m", "build", "--wheel", "-o", OUT],
        cwd=DIR,
        env=ENV,
    )
    dist = set(OUT.glob("*.whl"))
    assert dist

@all_samples
def test_sample_pip_wheel(sample, tmp_path):
    maybe_skip(sample)
    DIR = ROOT / "samples" / sample
    OUT = tmp_path / "out"
    subprocess.check_call(
        [sys.executable, "-m", "pip", "wheel", DIR, "-w", OUT],
        env=ENV,
    )
    dist = set(OUT.glob("*.whl"))
    assert dist

@all_samples
def test_sample_pip_from_sdist(sample, tmp_path):
    maybe_skip(sample)
    DIR = ROOT / "samples" / sample
    OUT = tmp_path / "out"
    subprocess.check_call(
        [sys.executable, "-m", "build", "--sdist", "-o", OUT],
        cwd=DIR,
        env=ENV,
    )
    dist = set(OUT.glob("*.tar.gz"))
    assert dist
    for d in dist:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "wheel", d, "-w", OUT],
            cwd=DIR,
            env=ENV,
        )
        whls = set(OUT.glob("*.whl"))
        assert whls
        for w in whls:
            w.unlink()

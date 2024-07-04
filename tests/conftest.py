import os
import pytest

from pathlib import Path

@pytest.fixture(scope="session")
def testdata():
    try:
        return Path(os.environ["PYMSBUILD_TEST_TESTDATA"])
    except KeyError:
        return Path(__file__).absolute().parent

@pytest.fixture(scope="session")
def inittestprojects(testdata):
    return testdata / "testinit"

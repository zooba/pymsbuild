import pytest

from pathlib import Path

@pytest.fixture(scope="session")
def testdata():
    return Path(__file__).absolute().parent / "testdata"

@pytest.fixture(scope="session")
def inittestprojects():
    return Path(__file__).absolute().parent / "testinit"

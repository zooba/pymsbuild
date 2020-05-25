import pytest

from pathlib import Path

@pytest.fixture(scope="session")
def testdata():
    return Path(__file__).absolute().parent / "testdata"

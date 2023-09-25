import os
import sys
import warnings

audit_events = []

def event_hook(event_name, args):
    if event_name.startswith("pymsbuild."):
        audit_events.append((event_name, args))

sys.addaudithook(event_hook)

#######################################
# Check testdllpack
#######################################
try:
    import testdllpack as TDP
finally:
    print(*audit_events, sep="\n")
print("Successful import of: ", TDP.__file__)
print(dir(TDP))

assert audit_events[0] == ("pymsbuild.dllpack.lookup_import", ("testdllpack", "testdllpack"))
assert audit_events[1][0] == "pymsbuild.dllpack.load_pyc"
if audit_events[2][0] == "pymsbuild.dllpack.decrypt_buffer":
    assert audit_events[3] == ("pymsbuild.dllpack.data_names", ("testdllpack",))
else:
    assert audit_events[2] == ("pymsbuild.dllpack.data_names", ("testdllpack",))

assert os.path.isabs(TDP.__file__)
assert not os.path.exists(TDP.__file__)
assert os.path.splitext(TDP.__file__)[1].lower() == ".py"

assert TDP.__spec__.origin == TDP.__file__
assert TDP.__spec__.name == "testdllpack"
assert TDP.__spec__.submodule_search_locations == TDP.__path__ == []
assert TDP.INIT_MEMBER

#######################################
# Check testdllpack.mod1
#######################################
import testdllpack.mod1 as M1
print("Successful import of: ", M1.__file__)
print(dir(M1))

assert os.path.isabs(M1.__file__)
assert not os.path.exists(M1.__file__)
assert os.path.splitext(M1.__file__)[1].lower() == ".py"

assert M1.__spec__.origin == M1.__file__
assert M1.__spec__.name == "testdllpack.mod1"
assert M1.__path__ is None
assert M1.MOD1_MEMBER

assert TDP.mod1 is M1

#######################################
# Check testdllpack.sub.mod2
#######################################
import testdllpack.sub.mod2 as M2
print("Successful import of: ", M2.__file__)
print(dir(M2))

assert os.path.isabs(M2.__file__)
assert not os.path.exists(M2.__file__)
assert os.path.splitext(M2.__file__)[1].lower() == ".py"

assert M2.__spec__.origin == M2.__file__
assert M2.__spec__.name == "testdllpack.sub.mod2"
assert M2.__path__ is None
assert M2.MOD2_MEMBER

assert TDP.sub.mod2 is M2

#######################################
# Check testdllpack/data.txt
#######################################
import importlib.resources as i_r
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    c = list(i_r.contents(TDP))
print(c)
assert "data.txt" in c

# importlib.resources has no feature detection, so we have to assume that
# they'll stick to CPython versions.
if sys.version_info[:2] >= (3, 11):
    assert (i_r.files(TDP) / "data.txt").read_text().startswith("This is data")
    assert (i_r.files(TDP) / "data.txt").read_bytes().startswith(b"This is data")

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    assert i_r.read_text(TDP, "data.txt", encoding="ascii").startswith("This is data")
    assert i_r.read_binary(TDP, "data.txt").startswith(b"This is data")
    with i_r.path(TDP, "data.txt") as f:
        with open(f, "rb") as f2:
            c = f2.read()
        assert c == i_r.read_binary(TDP, "data.txt")

assert not os.path.isfile(f)

#######################################
# Check testdllpack/test-dllpack.py
#######################################
try:
    __import__("testdllpack.test-dllpack")
except ModuleNotFoundError:
    pass
try:
    __import__("testdllpack.test-dllpack.py")
except ModuleNotFoundError:
    pass

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    c = i_r.read_text(TDP, "test-dllpack.py")
assert c

#######################################
# Check pretend.pyd
#######################################

try:
    import testdllpack_pretend
except ModuleNotFoundError:
    # We expect the module to be found ...
    raise
except ImportError:
    # ... but it should fail to load (because it's not real)
    pass

try:
    import pretend
except ModuleNotFoundError:
    # We expect the module to be found ...
    raise
except ImportError:
    # ... but it should fail to load (because it's not real)
    pass

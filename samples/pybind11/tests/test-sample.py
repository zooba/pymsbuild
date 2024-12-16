from pybind11_sample.example import add

print(add(1, 2), "== 3")
assert add(1, 2) == 3

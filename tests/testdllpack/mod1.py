# mod1.py
print("This is mod1.py at", __file__)

import importlib.resources
print(importlib.resources.read_text("testdllpack", "data.txt"))

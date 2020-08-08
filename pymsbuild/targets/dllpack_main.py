def _init():
    import sys

    from importlib import import_module
    from importlib.abc import Loader, MetaPathFinder, ResourceReader
    from importlib.machinery import ModuleSpec
    from ntpath import split as nt_split

    _NAME = NAME()
    _NAME_DOT = _NAME + "."
    _MAKESPEC = MAKESPEC
    _DATA = DATA
    _DATA_NAMES = set(DATA_NAMES())

    class DllPackReader(ResourceReader):
        def __init__(self, prefix):
            self.prefix = prefix

        def open_resource(self, resource):
            import io
            return io.BytesIO(_DATA(self.prefix + resource))

        def resource_path(self, resource):
            raise FileNotFoundError()

        def is_resource(self, resource):
            return prefix + resource in _DATA_NAMES

        def contents(self):
            return (n for n in _DATA_NAMES if n.startswith(self.prefix))

    DllPackReader.__name__ += "_" + _NAME
    DllPackReader.__qualname__ = "<generated>." + DllPackReader.__name__


    class DllPackLoader(Loader):
        create_module = CREATE_MODULE
        exec_module = EXEC_MODULE

        def get_resource_reader(self, fullname):
            try:
                spec = _MAKESPEC(fullname, LOADER)
                if spec.submodule_search_locations is None:
                    return None
            except Exception:
                return None
            return DllPackReader(fullname + ".")

    DllPackLoader.__name__ += "_" + _NAME
    DllPackLoader.__qualname__ = "<generated>." + DllPackLoader.__name__

    LOADER = DllPackLoader()


    class DllPackFinder(MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            if fullname.startswith(_NAME_DOT) or fullname == _NAME:
                return _MAKESPEC(fullname, LOADER)

    DllPackFinder.__name__ += "_" + _NAME
    DllPackFinder.__qualname__ = "<generated>." + DllPackFinder.__name__

    FINDER = next((m.__name__ == DllPackFinder.__name__ for m in sys.meta_path), None)
    if not FINDER:
        FINDER = DllPackFinder()
        sys.meta_path.append(FINDER)

    return _MAKESPEC(__name__, LOADER)


__spec__ = _init()
del _init, NAME, CREATE_MODULE, EXEC_MODULE, DATA, DATA_NAMES, MAKESPEC

__file__ = __spec__.origin
__loader__ = __spec__.loader
__path__ = []

def _init():
    import sys
    from importlib.abc import Loader, MetaPathFinder, PathEntryFinder
    from importlib.machinery import ExtensionFileLoader
    try:
        from importlib.resources.abc import TraversalError
    except ImportError:
        class TraversalError(Exception): pass

    _NAME = __NAME()
    _NAME_DOT = _NAME + "."
    _MAKESPEC = __MAKESPEC
    _DATA = __DATA
    _DATA_NAMES = set(__DATA_NAMES())
    _CREATE_MODULE = __CREATE_MODULE
    _EXEC_MODULE = __EXEC_MODULE
    _MODULE_NAMES = __MODULE_NAMES

    class DllPackReader:
        class Traversable:
            def __init__(self, name, prefix):
                self.name = name
                self._prefix = prefix

            def iterdir(self):
                p =  self._prefix + self.name + "."
                lp = len(p)
                return (type(self)(n[lp:], p) for n in _DATA_NAMES if n.startswith(p))

            def read_bytes(self):
                return _DATA(self._prefix + self.name)

            def read_text(self, encoding="utf-8", errors="strict"):
                return self.read_bytes().decode(encoding, errors)

            def is_dir(self):
                return any(self.iterdir())

            def is_file(self):
                return not any(self.iterdir())

            def joinpath(self, *paths):
                prefix = self._prefix + self.name + "/" + "/".join(paths).replace("\\", "/")
                prefix, _, name = prefix.rpartition("/")
                prefix = prefix.replace("/", ".") + "."
                if prefix + name not in _DATA_NAMES:
                    raise TraversalError("resource not found: " + prefix + name)
                return type(self)(name, prefix)

            def __truediv__(self, path):
                return self.joinpath(path)

            def open(self, mode='r', *args, **kwargs):
                if mode not in ('r', 'rb'):
                    raise ValueError("unsupported mode: " + mode)
                import io
                o = io.BytesIO(self.read_bytes())
                if mode == 'r':
                    return io.TextIOWrapper(o, *args, **kwargs)
                return o

        def __init__(self, prefix):
            self.prefix = prefix

        def open_resource(self, resource):
            import io
            return io.BytesIO(_DATA(self.prefix + resource))

        def resource_path(self, resource):
            raise FileNotFoundError()

        def is_resource(self, resource):
            return self.prefix + resource in _DATA_NAMES

        def contents(self):
            p = self.prefix
            lp = len(p)
            return (n[lp:] for n in _DATA_NAMES if n.startswith(p))

        def files(self):
            return self.Traversable(self.prefix.strip("."), "")


    DllPackReader.__name__ += "_" + _NAME
    DllPackReader.__qualname__ = "<generated>." + DllPackReader.__name__

    class DllPackLoader(Loader):
        create_module = _CREATE_MODULE
        exec_module = _EXEC_MODULE

        def get_resource_reader(self, fullname):
            try:
                spec = _MAKESPEC(fullname, LOADER, None)
                if spec.submodule_search_locations is None:
                    return None
            except Exception:
                return None
            return DllPackReader(fullname + ".")

    DllPackLoader.__name__ += "_" + _NAME
    DllPackLoader.__qualname__ = "<generated>." + DllPackLoader.__name__

    LOADER = DllPackLoader()

    class DllPackFinder(MetaPathFinder):
        _PATH_HOOK_PREFIX = "$dllpack:" + _NAME

        def __init__(self, prefix):
            self._prefix = prefix

        @classmethod
        def find_spec(cls, fullname, path=None, target=None):
            if fullname.startswith(_NAME_DOT) or fullname == _NAME:
                spec = _MAKESPEC(fullname, LOADER, "$dllpack:" + fullname)
                if spec and not spec.loader:
                    spec.loader = ExtensionFileLoader(spec.name, spec.origin)
                return spec

        def iter_modules(self, prefix):
            if not prefix:
                prefix = self._prefix
            return _MODULE_NAMES(prefix)

        @classmethod
        def hook(cls, path):
            if path.startswith(cls._PATH_HOOK_PREFIX):
                return cls(path[len("$dllpack:"):])
            raise ImportError()

    DllPackFinder.__name__ += "_" + _NAME
    DllPackFinder.__qualname__ = "<generated>." + DllPackFinder.__name__

    if not any(getattr(m, "__name__", None) == DllPackFinder.__name__ for m in sys.meta_path):
        sys.meta_path.insert(0, DllPackFinder)
        sys.path_hooks.append(DllPackFinder.hook)

    return _MAKESPEC(__name__, LOADER, DllPackFinder._PATH_HOOK_PREFIX)


__spec__ = _init()
__file__ = __spec__.origin
__loader__ = __spec__.loader
__package__ = getattr(__spec__, "parent", None)
__path__ = __spec__.submodule_search_locations
del _init, __CREATE_MODULE, __DATA, __DATA_NAMES, __EXEC_MODULE, __MODULE_NAMES, __MAKESPEC, __NAME

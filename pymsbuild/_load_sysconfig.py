from pathlib import Path

def read_sysconfig_from_file(text):
    import ast

    data = {}

    class Visitor(ast.NodeVisitor):
        def visit_Assign(self, n):
            if (n.targets
                and isinstance(n.targets[0], ast.Name)
                and n.targets[0].id == "build_time_vars"
                and isinstance(n.value, ast.Dict)
            ):
                for k, v in zip(n.value.keys, n.value.values):
                    if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                        data[k.value] = v.value
                    # Handle pre-3.8, just in case
                    elif hasattr(ast, "Str"):
                        if isinstance(k, ast.Str) and isinstance(v, ast.Str):
                            data[k.s] = v.s

    tree = ast.parse(text)
    Visitor().visit(tree)
    return data


def load_sysconfig(file=None):
    if file:
        data = read_sysconfig_from_file(Path(file).read_text(encoding="utf-8"))
        data["__FROM_FILE"] = str(file)
    else:
        import sysconfig
        data = sysconfig.get_config_vars()
        for k in [k for k in data if k.startswith(("HAVE_", "DOUBLE_IS_", "PY_SSL"))]:
            data.pop(k, None)

    if "SO" not in data:
        data["SO"] = f".{data['SOABI']}{data['SHLIB_SUFFIX']}"

    return data


if __name__ == "__main__":
    import pprint
    import sys
    pprint.pprint(load_sysconfig(sys.argv[1] if len(sys.argv) > 1 else None))

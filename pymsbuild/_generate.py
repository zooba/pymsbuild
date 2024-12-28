import os
import sys

from pathlib import PurePath, Path
from ._types import Package, CProject, File, LiteralXML, Property, ItemDefinition, ConditionalValue
from ._writer import ProjectFileWriter

from importlib.machinery import EXTENSION_SUFFIXES
DEFAULT_PYD_SUFFIX = EXTENSION_SUFFIXES[-1]

LIBPATH = Path(sys.base_prefix) / "libs"
INCPATH = Path(sys.base_prefix) / "include"
SEP = os.path.sep

class GroupSwitcher:
    def __init__(self, project):
        self.project = project
        self.tag = None
        self._cm = None

    def switch_to(self, tag):
        if tag == self.tag:
            return
        if self._cm:
            self._cm.__exit__(None, None, None)
            self._cm = None
        if tag:
            self._cm = self.project.group(tag)
            self._cm.__enter__()
        self.tag = tag

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        if self._cm:
            return self._cm.__exit__(*exc_info)


def _resolve_wildcards(basename, source, pattern):
    """Find all files matching 'pattern' under 'source'.

Returns a sequence of (generated name, path), where each element may be
a Path, PurePath, or str. If there are no wildcards in 'pattern', the
generated name is 'basename' unmodified and the path is
"source / pattern". Otherwise, 'basename' is reduced by the same number
of segments as there are in 'pattern', and the generated name for each
file will be the recursive path appended to the shortened base.

The filename in 'basename' is preserved if the filename in 'pattern'
contains no wildcard characters. Otherwise, the filename in the
returned basenames are replaced by the matched filenames.

If 'pattern' is an absolute path, it is split at the first wildcard
segment and the first part becomes 'source'. 'basename' must have at
least as many segments as remain in 'pattern'.
"""
    basename = PurePath(basename)
    pattern = PurePath(pattern)

    if pattern.is_absolute():
        for i, p in enumerate(pattern.parts):
            if "*" in p or "?" in p:
                source /= PurePath(*pattern.parts[:i])
                pattern = PurePath(*pattern.parts[i:])
                break
        else:
            yield basename, pattern
            return

    # Keep the basename if the pattern name is not a wildcard.
    # Otherwise, we'll replace with the matched filenames
    finalname = None if ("*" in pattern.name or "?" in pattern.name) else basename.name
    basename = basename.parent

    pattern_parts = list(pattern.parts)
    while pattern_parts:
        p = pattern_parts[0]
        if "*" in p or "?" in p:
            break
        source /= p
        del pattern_parts[0]
    else:
        yield basename / finalname, source
        return

    if finalname:
        def _make_basename(bn, p, d):
            return (bn / p.relative_to(d)).with_name(finalname)
    else:
        def _make_basename(bn, p, d):
            return bn / p.relative_to(d)

    roots = [(basename, source)]
    for i, r in enumerate(pattern_parts[:-1]):
        if r == "**":
            wildcards = str(PurePath(*pattern_parts[i + 1:]))
            yield from ((_make_basename(bn, p, d), p)
                        for bn, d in roots
                        for p in d.rglob("*")
                        if not p.is_dir() and p.relative_to(d).match(wildcards))
            return
        roots = [((bn / p.name), p) for bn, d in roots for p in d.glob(r) if p.is_dir()]

    r = pattern.parts[-1]
    yield from ((bn / (finalname or p.name), p) for bn, d in roots for p in d.glob(r) if not p.is_dir())


def _all_members(item, recurse_if=None, return_if=None, *, prefix="", make_prefix=None):
    if make_prefix is None:
        make_prefix = lambda p, i: "{}{}/".format(p, i.name)
    if not return_if or return_if(item):
        yield "{}{}".format(prefix, item.name), item
    if not recurse_if or recurse_if(item):
        for m in item.members:
            yield from _all_members(
                m,
                recurse_if,
                return_if,
                prefix=make_prefix(prefix, item),
                make_prefix=make_prefix,
            )


def _write_file_with_wildcards(f, source_dir, name, item):
    wrote_any = bool(item.options.get("allow_none"))
    flat_char = item.options.get("flatten")
    new_name = item.options.get("Name")
    exclude = ()
    condition = None
    if getattr(item, "has_condition", False):
        condition = getattr(item, "condition", None)
        patterns = (getattr(item, "exclude", None) or "").split(os.pathsep)
        exclude = set()
        for pattern in patterns:
            exclude.update(p2 for n2, p2 in _resolve_wildcards(name, source_dir, pattern))
    for n2, p2 in _resolve_wildcards(name, source_dir, item.source):
        if p2 in exclude:
            continue
        if isinstance(new_name, str):
            n2 = n2.with_name(new_name)
        if flat_char is True:
            n2 = n2.parts[-1]
        elif isinstance(flat_char, str):
            n2 = flat_char.join(n2.parts)
        options = {
            "SourceDir": source_dir,
            **item.options,
            "Name": n2,
            "allow_none": None,
            "flatten": None,
        }
        if new_name is not None and not isinstance(new_name, str):
            options["Name"] = new_name
        if condition:
            p2 = ConditionalValue(p2, condition=condition)
        f.add_item(item._ITEMNAME, p2, **options)
        wrote_any = True
    if not wrote_any:
        raise ValueError("failed to find any files for {} in {}".format(
            item.source, source_dir))


def _write_members(f, source_dir, members):
    with GroupSwitcher(f) as g:
        for n, p in members:
            if isinstance(p, File):
                g.switch_to("ItemGroup")
                if "$(" not in str(p.source):
                    _write_file_with_wildcards(f, source_dir, n, p)
                else:
                    f.add_item(p._ITEMNAME, p.source, **{
                        "SourceDir": source_dir,
                        "Name": n,
                        **p.options,
                    })
            elif isinstance(p, Property):
                g.switch_to("PropertyGroup")
                f.add_property(p.name, p.value)
            elif isinstance(p, ItemDefinition):
                g.switch_to("ItemDefinitionGroup")
                with f.group(p.kind):
                    for k, v in p.options.items():
                        f.add_item_property(p.kind, k, v)
            elif isinstance(p, LiteralXML):
                g.switch_to(None)
                f.add_text(p.xml)
            elif hasattr(p, "write_member"):
                p.write_member(f, g)


def _generate_c_project(project, build_dir, root_dir):
    build_dir = Path(build_dir)
    proj = build_dir / "{}.proj".format(project.name)
    root_dir = Path(root_dir)
    source_dir = root_dir / project.source

    if project.project_file:
        return Path(project.project_file)

    tname = project.options.get("TargetName", project.name)
    with ProjectFileWriter(proj, tname, vc_platforms=True, root_namespace=project.name) as f:
        with f.group("PropertyGroup", Label="Globals"):
            f.add_property("SourceDir", ConditionalValue(source_dir, if_empty=True))
            f.add_property("SourceRootDir", ConditionalValue(root_dir, if_empty=True))
        _write_project_references(f, project, build_dir, source_dir)
        _write_members(f, source_dir, _all_members(project, recurse_if=lambda m: m is project))
        for n, p in _all_members(project, recurse_if=lambda m: m is project, return_if=lambda m: isinstance(m, Package)):
            _write_members(
                f,
                source_dir,
                _all_members(p, recurse_if=lambda m: not isinstance(m, CProject), prefix=f"{project.name}/")
            )

    return proj


def _generate_reference_metadata(relname, project, source_dir):
    tname = project.options.get("TargetName", relname.stem)
    tdir = str(relname.parent)
    return {
        "TargetDir": "" if tdir == "." else tdir,
        "IntDir": "$(IntDir)" + tname,
        "ParentNamespace": ".".join(relname.parent.parts),
        **project.options,
        "SourceDir": source_dir / project.source,
    }


def _write_project_references(f, project, build_dir, source_dir):
    with f.group("ItemGroup", Label="ProjectReferences"):
        for n, p in _all_members(
            project,
            return_if=lambda m: m is not project and isinstance(m, CProject),
            make_prefix=lambda prefix, item: "{}{}/".format(prefix, item.name) if not isinstance(item, CProject) else prefix,
        ):
            fn = PurePath(n)
            pdir = _generate_c_project(p, build_dir, source_dir)
            try:
                pdir = pdir.relative_to(Path(f.filename).parent)
            except ValueError:
                pass
            f.add_item(
                "Project",
                pdir,
                Name=n,
                **_generate_reference_metadata(fn, p, source_dir),
            )


def generate(project, build_dir, source_dir, config_file=None):
    build_dir = Path(build_dir)
    root_dir = Path(source_dir)
    config_file = root_dir / (config_file or "_msbuild.py")
    source_dir = root_dir / project.source
    proj = build_dir / "{}.proj".format(project.name)

    if project.project_file:
        return Path(project.project_file)

    if isinstance(project, CProject):
        return _generate_c_project(project, build_dir, root_dir)

    with ProjectFileWriter(proj, project.name) as f:
        with f.group("PropertyGroup"):
            f.add_property("SourceDir", ConditionalValue(source_dir, if_empty=True))
            f.add_property("SourceRootDir", ConditionalValue(root_dir, if_empty=True))
            f.add_property("IncludePyprojectToml", ConditionalValue("true", if_empty=True))
            for k, v in project.options.items():
                f.add_property(k, v)
        f.add_import(f"$(PyMsbuildTargets){SEP}common.props")
        f.add_import(f"$(PyMsbuildTargets){SEP}package.props")
        _write_project_references(f, project, build_dir, source_dir)
        with f.group("ItemGroup", Label="Sdist metadata"):
            f.add_item("Sdist", build_dir / "PKG-INFO", RelativeSource="PKG-INFO")
            f.add_item("Sdist", config_file, RelativeSource="_msbuild.py")
        _write_members(f, source_dir, _all_members(
            project,
            recurse_if=lambda m: not isinstance(m, CProject),
        ))
        f.add_import(f"$(PyMsbuildTargets){SEP}common.targets")
        f.add_import(f"$(PyMsbuildTargets){SEP}package.targets")

    return proj


def _write_metadata(f, key, value, source_dir):
    if not isinstance(value, str) and hasattr(value, "__iter__"):
        for v in value:
            _write_metadata(f, key, v, source_dir)
        return
    if isinstance(value, File):
        value = (source_dir / value.source).read_text(encoding="utf-8")
    if "\n" in value:
        value = value.replace("\n", "\n       |")
    print(key, value, sep=": ", file=f)


def _write_metadata_description(f, value, source_dir):
    if not isinstance(value, str) and hasattr(value, "__iter__"):
        for v in value:
            _write_metadata_description(f, v, source_dir)
        return
    if isinstance(value, File):
        value = (source_dir / value.source).read_text(encoding="utf-8")
    print(file=f)
    print(value, file=f)


def generate_distinfo(distinfo, build_dir, source_dir):
    build_dir.mkdir(parents=True, exist_ok=True)
    with (build_dir / "PKG-INFO").open("w", encoding="utf-8") as f:
        description = None
        for k, vv in distinfo.items():
            if k.casefold() == "description".casefold():
                description = vv
                continue
            _write_metadata(f, k, vv, source_dir)
        if description:
            _write_metadata_description(f, description, source_dir)

def readback_distinfo(pkg_info):
    distinfo = []
    description = None
    with open(pkg_info, "r", encoding="utf-8") as f:
        for line in f:
            if description is not None:
                description.append(line)
                continue
            line = line.rstrip()
            if not line:
                description = []
                continue
            if line.startswith(("       |", "        ")):
                distinfo[-1] = (distinfo[-1][0], distinfo[-1][1] + "\n" + line[8:])
                continue
            key, _, value = line.partition(":")
            distinfo.append((key.strip(), value.lstrip()))
    d = {}
    for k, v in distinfo:
        r = d.get(k, None)
        if isinstance(r, list):
            r.append(v)
        elif r is not None and r is not v:
            d[k] = [r, v]
        else:
            d[k] = v
    if description:
        d["Description"] = "".join(description).rstrip()
    return d

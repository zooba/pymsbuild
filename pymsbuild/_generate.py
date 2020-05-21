import sys

from pathlib import PureWindowsPath as PurePath, WindowsPath as Path
from ._types import PydFile, File, LiteralXML, Property, ItemDefinition, ConditionalValue
from ._writer import ProjectFileWriter

LIBPATH = Path(sys.base_prefix) / "libs"
INCPATH = Path(sys.base_prefix) / "include"


def _all_members(item, recurse_if=None, return_if=None, *, prefix=""):
    if not return_if or return_if(item):
        yield "{}{}".format(prefix, item.name), item
    if not recurse_if or recurse_if(item):
        for m in item._members:
            yield from _all_members(
                m,
                recurse_if,
                return_if,
                prefix="{}{}/".format(prefix, item.name),
            )


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


def _resolve_wildcards(basename, source):
    if source.parent.name == "**":
        for d in source.parent.parent.iterdir():
            if d.is_dir():
                yield from _resolve_wildcards(basename, d / source.name)
    elif "*" in source.name or "?" in source.name:
        name = PurePath(basename)
        for p in source.parent.glob(source.name):
            yield name.parent / p.name, p
    else:
        yield basename, source

def _write_members(f, source_dir, members):
    with GroupSwitcher(f) as g:
        for n, p in members:
            if isinstance(p, File):
                g.switch_to("ItemGroup")
                wrote_any = False
                for n2, p2 in _resolve_wildcards(n, source_dir / p.source):
                    f.add_item(p._ITEMNAME, p2, Name=n2, **p.options)
                    wrote_any = True
                if not wrote_any:
                    raise ValueError("failed to find any files for " + str(p.source))
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


def _generate_pyd(project, build_dir, source_dir):
    build_dir = Path(build_dir)
    proj = build_dir / "{}.proj".format(project.name)

    if project.project_file:
        return Path(project.project_file)

    with ProjectFileWriter(proj, project.name, vc_platforms=True) as f:
        with f.group("PropertyGroup", Label="Globals"):
            f.add_property("OutDir", "layout\\")
            f.add_property("IntDir", ConditionalValue("build\\", if_empty=True))
        f.add_import("$(VCTargetsPath)\Microsoft.Cpp.Default.props")
        f.add_import(r"$(PyMsbuildTargets)\common.props")
        with f.group("PropertyGroup", Label="Configuration"):
            f.add_property("ConfigurationType", project.options.get("ConfigurationType", "DynamicLibrary"))
            f.add_property("PlatformToolset", "$(DefaultPlatformToolset)")
            f.add_property("CharacterSet", "Unicode")
        f.add_import("$(VCTargetsPath)\Microsoft.Cpp.props")
        with f.group("PropertyGroup"):
            f.add_property("TargetExt", project.options.get("TargetExt", ".pyd"))
            f.add_property("LinkIncremental", "false")
        with f.group("ItemDefinitionGroup"):
            with f.group("ClCompile"):
                f.add_property("AdditionalIncludeDirectories", "{};%(AdditionalIncludeDirectories)".format(INCPATH)),
            with f.group("Link"):
                f.add_property("AdditionalLibraryDirectories", "{};%(AdditionalLibraryDirectories)".format(LIBPATH)),
                f.add_property("GenerateDebugInformation", "True")

        _write_members(f, source_dir, _all_members(project, recurse_if=lambda m: m is project))

        f.add_import(r"$(PyMsbuildTargets)\common.targets")
        f.add_import(r"$(VCTargetsPath)\Microsoft.Cpp.targets")
        f.add_import(r"$(PyMsbuildTargets)\pyd.targets")
        f.add_import(r"$(PyMsbuildTargets)\sdist.targets")

    return proj


def generate(project, build_dir, source_dir):
    build_dir = Path(build_dir)
    source_dir = Path(source_dir)
    proj = build_dir / "{}.proj".format(project.name)

    if project.project_file:
        return Path(project.project_file)

    with ProjectFileWriter(proj, project.name) as f:
        with f.group("PropertyGroup"):
            f.add_property("SourceDir", ConditionalValue(".", if_empty=True))
            f.add_property("OutDir", ConditionalValue("layout\\", if_empty=True))
            f.add_property("IntDir", ConditionalValue("build\\", if_empty=True))
        f.add_import(r"$(PyMsbuildTargets)\common.props")
        with f.group("ItemGroup", Label="ProjectReferences"):
            for n, p in _all_members(project, return_if=lambda m: isinstance(m, PydFile)):
                fn = PurePath(n)
                pdir = _generate_pyd(p, build_dir, source_dir)
                try:
                    pdir = pdir.relative_to(proj.parent)
                except ValueError:
                    pass
                f.add_item(
                    "Project",
                    pdir,
                    Name=n,
                    **{
                        **dict(
                            TargetDir=fn.parent,
                            TargetName=fn.stem,
                            TargetExt=".pyd",
                        ),
                        **p.options,
                    }
                )
        with f.group("ItemGroup", Label="Sdist metadata"):
            f.add_item("Sdist", build_dir / "PKG_INFO", RelativeSource="PKG_INFO")
            f.add_item("Sdist", source_dir / "_msbuild.py", RelativeSource="_msbuild.py")
            f.add_item("Sdist", source_dir / "pyproject.toml", RelativeSource="pyproject.toml")
        _write_members(f, source_dir, _all_members(
            project,
            recurse_if=lambda m: not isinstance(m, PydFile),
        ))
        f.add_import(r"$(PyMsbuildTargets)\common.targets")
        f.add_import(r"$(PyMsbuildTargets)\package.targets")
        f.add_import(r"$(PyMsbuildTargets)\sdist.targets")

    return proj


def _write_metadata(f, key, value, source_dir):
    if not isinstance(value, str) and hasattr(value, "__iter__"):
        for v in value:
            _write_metadata(f, key, v, source_dir)
        return
    if isinstance(value, File):
        values = (source_dir / value.source).read_text(encoding="utf-8")
    if "\n" in value:
        values = value.replace("\n", "\n       |")
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
    with (build_dir / "PKG_INFO").open("w", encoding="utf-8") as f:
        description = None
        for k, vv in distinfo.items():
            if k.casefold() == "description".casefold():
                description = vv
                continue
            _write_metadata(f, k, vv, source_dir)
        if description:
            _write_metadata_description(f, description, source_dir)

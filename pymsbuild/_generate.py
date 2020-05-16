from pathlib import PureWindowsPath as PurePath, WindowsPath as Path
from ._types import PydFile, File


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


def _generate_pyd(project, build_dir, source_dir):
    build_dir = Path(build_dir)
    proj = build_dir / "{}.proj".format(project.name)

    if project.project_file:
        return Path(project.project_file)

    import pymsbuild.template as T
    with T.ProjectFileWriter(proj, project.name, vc_platforms=True) as f:
        f.add_import("$(VCTargetsPath)\Microsoft.Cpp.Default.props")
        with f.group("PropertyGroup", Label="Configuration"):
            f.add_property("ConfigurationType", project.options.get("ConfigurationType", "DynamicLibrary"))
            f.add_property("PlatformToolset", "$(DefaultPlatformToolset)")
            f.add_property("CharacterSet", "Unicode")
        f.add_import("$(VCTargetsPath)\Microsoft.Cpp.props")
        with f.group("PropertyGroup"):
            f.add_property("TargetExt", project.options.get("TargetExt", ".pyd"))
            f.add_property("LinkIncremental", "false")
        with f.group("ItemDefinitionGroup"):
            with f.group("Link"):
                f.add_property("GenerateDebugInformation", "True")

        with f.group("ItemGroup"):
            for n, p in _all_members(
                project,
                return_if=lambda m: isinstance(m, File),
                recurse_if=lambda m: m is project
            ):
                f.add_item(
                    p._ITEMNAME,
                    source_dir / p.source,
                    RelativeSource=p.source,
                )

        f.add_import("$(VCTargetsPath)\Microsoft.Cpp.targets")
        f.add_text(T.VCTARGETS)

    return proj


def generate(project, build_dir, source_dir):
    build_dir = Path(build_dir)
    source_dir = Path(source_dir)
    proj = build_dir / "{}.proj".format(project.name)

    if project.project_file:
        return Path(project.project_file)

    import pymsbuild.template as T
    with T.ProjectFileWriter(proj, project.name) as f:
        with f.group("PropertyGroup"):
            f.add_property("_ProjectBuildTarget", "Build", if_empty=True)
            f.add_property("OutDir", "layout\\", condition="$(_ProjectBuildTarget) == 'Build'")
            f.add_property("OutDir", "$(MSBuildThisProjectDirectory)", condition="$(_ProjectBuildTarget) == 'BuildSdist'")
            f.add_property("IntDir", "build\\", if_empty=True)
        with f.group("ItemGroup", Label="ProjectReferences"):
            for n, p in _all_members(project, return_if=lambda m: isinstance(m, PydFile)):
                fn = PurePath(n)
                pdir = _generate_pyd(p, build_dir, source_dir)
                if proj.parent == Path(*pdir.parts[:len(proj.parent.parts)]):
                    pdir = pdir.relative_to(proj.parent)
                f.add_item(
                    "Project",
                    pdir,
                    Name=n,
                    TargetDir=fn.parent,
                    TargetName=fn.stem,
                    TargetExt=p.options.get("TargetExt", ".pyd"),
                )
        with f.group("ItemGroup"):
            for n, p in _all_members(
                project,
                return_if=lambda m: isinstance(m, File),
                recurse_if=lambda m: not isinstance(m, PydFile),
            ):
                fn = PurePath(n)
                f.add_item(
                    p._ITEMNAME,
                    source_dir / p.source,
                    Name=n,
                    RelativeSource=p.source,
                    TargetDir=fn.parent,
                    TargetName=fn.stem,
                    TargetExt=fn.suffix
                )
        f.add_text(T.TARGETS)

    return proj

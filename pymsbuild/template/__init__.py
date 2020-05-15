from importlib.resources import read_text
from pathlib import PurePath
import uuid

_GENERATED_NAMESPACE = uuid.UUID('db509c23-800c-41d5-9d00-359fc120e87a')

PROLOGUE = read_text("pymsbuild.template", "prologue.txt").rstrip()
VCPLATFORMS = read_text("pymsbuild.template", "vcplatforms.txt").rstrip()
_PROPERTIES = read_text("pymsbuild.template", "properties.txt.in").rstrip()
_VCPROPERTIES = read_text("pymsbuild.template", "vcproperties.txt.in").rstrip()
ITEMS_START = read_text("pymsbuild.template", "items_start.txt").rstrip()
# Items go here
ITEMS_END = read_text("pymsbuild.template", "items_end.txt").rstrip()
TARGETS = read_text("pymsbuild.template", "targets.txt").rstrip()
VCTARGETS = read_text("pymsbuild.template", "vctargets.txt").rstrip()
EPILOGUE = read_text("pymsbuild.template", "epilogue.txt").rstrip()


def _guid(project):
    return uuid.uuid3(_GENERATED_NAMESPACE, project.target_name)


def get_PROPERTIES(build_state, project):
    return _PROPERTIES.format(
        project=project,
        guid=_guid(project),
        distinfo=build_state.distinfo,
        **project.options,
    )


def get_VCPROPERTIES(build_state, project):
    return _VCPROPERTIES.format(
        project=project,
        guid=_guid(project),
        distinfo=build_state.distinfo,
        **project.options,
    )


def get_ITEM(kind, source, fullname):
    if kind == "Content":
        return r"""    <{kind} Include="$(SourceDir){source}">
        <Name>{name}</Name>
    </{kind}>""".format(
            kind=kind,
            name=PurePath(fullname).name,
            source=source,
            relpath=fullname,
        )
    elif kind == "Project":
        return r"""    <{kind} Include="{source}">
        <Name>{name}</Name>
    </{kind}>""".format(
            kind=kind,
            source=source,
            name=source.stem,
            relpath=fullname,
        )
    return r"""    <{kind} Include="$(SourceDir){source}" />""".format(
        kind=kind,
        source=source,
        name=fullname,
    )

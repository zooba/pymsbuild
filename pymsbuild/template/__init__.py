from importlib.resources import read_text
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


def get_PROPERTIES(build_state):
    return _PROPERTIES.format(
        project=build_state.project,
        guid=_guid(build_state.project),
        distinfo=build_state.distinfo,
        **build_state.project.options,
    )


def get_VCPROPERTIES(build_state):
    return _VCPROPERTIES.format(
        project=build_state.project,
        guid=_guid(build_state.project),
        distinfo=build_state.distinfo,
        **build_state.project.options,
    )


def get_ITEM(kind, source, fullname):
    if kind == "Content":
        return r"""    <Content Include="{source}">
        <Name>{name}</Name>
        <Destination>$(OutDir)\{relpath}</Destination>
    </Content>""".format(
            source=source,
            name=fullname.replace("\\", "."),
            relpath=fullname,
        )
    return r"""    <{kind} Include="{source}" />""".format(
        kind=kind,
        source=source,
        name=fullname,
    )

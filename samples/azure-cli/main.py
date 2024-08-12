import setuptools
try:
    import pywin32_bootstrap
except ModuleNotFoundError:
    pass

import azure.cli.core.aaz._command as aaz_command
import azure.cli.core._help_loaders as help_loaders
class HelpLoaderV2(help_loaders.BaseHelpLoader):
    @property
    def version(self):
        return 2

    def versioned_load(self, help_obj, parser):
        pass

    def get_noun_help_file_names(self, nouns):
        pass

    def load_entry_data(self, help_obj, parser):
        pass

    def load_help_body(self, help_obj):
        pass

    def load_help_parameters(self, help_obj):
        pass

    def load_help_examples(self, help_obj):
        pass

help_loaders.HelpLoaderV1 = HelpLoaderV2

def _load_aaz_pkg(loader, pkg, parent_command_table, command_group_table, arg_str, fully_load):
    """Override _load_aaz_pkg to use pkgutil to load rather than searching the disk
    """
    cut = False  # if cut, its sub commands and sub pkgs will not be added
    command_table = {}  # the command available for this pkg and its sub pkgs
    for value in pkg.__dict__.values():
        if not fully_load and cut and command_table:
            # when cut and command_table is not empty, stop loading more commands.
            # the command_table should not be empty.
            # Because if it's empty, the command group will be ignored in help if parent command group.
            break
        if isinstance(value, type):
            if issubclass(value, aaz_command.AAZCommandGroup):
                if value.AZ_NAME:
                    # AAZCommandGroup already be registered by register_command_command
                    if not arg_str.startswith(f'{value.AZ_NAME.lower()} '):
                        # when args not contain command group prefix, then cut more loading.
                        cut = True
                    # add command group into command group table
                    command_group_table[value.AZ_NAME] = value(
                        cli_ctx=loader.cli_ctx)  # add command group even it's cut
            elif issubclass(value, aaz_command.AAZCommand):
                if value.AZ_NAME:
                    # AAZCommand already be registered by register_command
                    command_table[value.AZ_NAME] = value(loader=loader)

    # continue load sub pkgs
    import pkgutil
    for mod in pkgutil.iter_modules(pkg.__path__):
        sub_path = mod.name
        if not fully_load and cut and command_table:
            # when cut and command_table is not empty, stop loading more sub pkgs.
            break
        if sub_path.startswith('_'):
            continue
        try:
            sub_pkg = aaz_command.importlib.import_module(f'.{sub_path}', pkg.__name__)
        except ModuleNotFoundError:
            aaz_command.logger.debug('Failed to load package folder in aaz: %s.',
                                     aaz_command.os.path.join(pkg_path, sub_path))
            continue

        # recursively load sub package
        _load_aaz_pkg(loader, sub_pkg, command_table, command_group_table, arg_str, fully_load)

    parent_command_table.update(command_table)  # update the parent pkg's command table.


aaz_command._load_aaz_pkg = _load_aaz_pkg


def run():
    import azure.cli.__main__

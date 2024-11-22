"""bump-my-version Command line interface."""

from pathlib import Path
from typing import List, Optional

import questionary
import rich_click as click
from click.core import Context
from tomlkit import dumps

from bumpversion import __version__
from bumpversion.bump import do_bump
from bumpversion.config import get_configuration
from bumpversion.config.create import create_configuration
from bumpversion.config.files import find_config_file
from bumpversion.context import get_context
from bumpversion.files import ConfiguredFile, modify_files
from bumpversion.show import do_show
from bumpversion.ui import get_indented_logger, print_info, setup_logging
from bumpversion.utils import get_overrides
from bumpversion.visualize import visualize

logger = get_indented_logger(__name__)


@click.group(
    context_settings={
        "help_option_names": ["-h", "--help"],
    },
    add_help_option=True,
)
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx: Context) -> None:
    """Version bump your Python project."""
    pass


click.rich_click.OPTION_GROUPS = {
    "bumpversion bump": [
        {
            "name": "Configuration",
            "options": [
                "--config-file",
                "--current-version",
                "--new-version",
                "--parse",
                "--serialize",
                "--search",
                "--replace",
                "--no-configured-files",
                "--ignore-missing-files",
                "--ignore-missing-version",
            ],
        },
        {
            "name": "Output",
            "options": ["--dry-run", "--verbose"],
        },
        {
            "name": "Committing and tagging",
            "options": [
                "--allow-dirty",
                "--commit",
                "--commit-args",
                "--message",
                "--tag",
                "--tag-name",
                "--tag-message",
                "--sign-tags",
            ],
        },
    ]
}


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument("args", nargs=-1, type=str)
@click.option(
    "--config-file",
    metavar="FILE",
    required=False,
    envvar="BUMPVERSION_CONFIG_FILE",
    type=click.Path(exists=True),
    help="Config file to read most of the variables from.",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    required=False,
    envvar="BUMPVERSION_VERBOSE",
    help="Print verbose logging to stderr. Can specify several times for more verbosity.",
)
@click.option(
    "--allow-dirty/--no-allow-dirty",
    default=None,
    required=False,
    envvar="BUMPVERSION_ALLOW_DIRTY",
    help="Don't abort if working directory is dirty, or explicitly abort if dirty.",
)
@click.option(
    "--current-version",
    metavar="VERSION",
    required=False,
    envvar="BUMPVERSION_CURRENT_VERSION",
    help="Version that needs to be updated",
)
@click.option(
    "--new-version",
    metavar="VERSION",
    required=False,
    envvar="BUMPVERSION_NEW_VERSION",
    help="New version that should be in the files",
)
@click.option(
    "--parse",
    metavar="REGEX",
    required=False,
    envvar="BUMPVERSION_PARSE",
    help="Regex parsing the version string",
)
@click.option(
    "--serialize",
    metavar="FORMAT",
    multiple=True,
    required=False,
    envvar="BUMPVERSION_SERIALIZE",
    help="How to format what is parsed back to a version",
)
@click.option(
    "--search",
    metavar="SEARCH",
    required=False,
    envvar="BUMPVERSION_SEARCH",
    help="Template for complete string to search",
)
@click.option(
    "--replace",
    metavar="REPLACE",
    required=False,
    envvar="BUMPVERSION_REPLACE",
    help="Template for complete string to replace",
)
@click.option(
    "--regex/--no-regex",
    default=None,
    envvar="BUMPVERSION_REGEX",
    help="Treat the search parameter as a regular expression or explicitly do not treat it as a regular expression.",
)
@click.option(
    "--no-configured-files",
    is_flag=True,
    envvar="BUMPVERSION_NO_CONFIGURED_FILES",
    help=(
        "Only replace the version in files specified on the command line, "
        "ignoring the files from the configuration file."
    ),
)
@click.option(
    "--ignore-missing-files/--no-ignore-missing-files",
    default=None,
    envvar="BUMPVERSION_IGNORE_MISSING_FILES",
    help="Ignore any missing files when searching and replacing in files.",
)
@click.option(
    "--ignore-missing-version/--no-ignore-missing-version",
    default=None,
    envvar="BUMPVERSION_IGNORE_MISSING_VERSION",
    help="Ignore any Version Not Found errors when searching and replacing in files.",
)
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    envvar="BUMPVERSION_DRY_RUN",
    help="Don't write any files, just pretend.",
)
@click.option(
    "--commit/--no-commit",
    default=None,
    envvar="BUMPVERSION_COMMIT",
    help="Commit to version control",
)
@click.option(
    "--tag/--no-tag",
    default=None,
    envvar="BUMPVERSION_TAG",
    help="Create a tag in version control",
)
@click.option(
    "--sign-tags/--no-sign-tags",
    default=None,
    envvar="BUMPVERSION_SIGN_TAGS",
    help="Sign tags if created",
)
@click.option(
    "--tag-name",
    metavar="TAG_NAME",
    required=False,
    envvar="BUMPVERSION_TAG_NAME",
    help="Tag name (only works with --tag)",
)
@click.option(
    "--tag-message",
    metavar="TAG_MESSAGE",
    required=False,
    envvar="BUMPVERSION_TAG_MESSAGE",
    help="Tag message",
)
@click.option(
    "-m",
    "--message",
    metavar="COMMIT_MSG",
    required=False,
    envvar="BUMPVERSION_MESSAGE",
    help="Commit message",
)
@click.option(
    "--commit-args",
    metavar="COMMIT_ARGS",
    required=False,
    envvar="BUMPVERSION_COMMIT_ARGS",
    help="Extra arguments to commit command",
)
def bump(
    # version_part: str,
    args: list,
    config_file: Optional[str],
    verbose: int,
    allow_dirty: Optional[bool],
    current_version: Optional[str],
    new_version: Optional[str],
    parse: Optional[str],
    serialize: Optional[List[str]],
    search: Optional[str],
    replace: Optional[str],
    regex: Optional[bool],
    no_configured_files: bool,
    ignore_missing_files: bool,
    ignore_missing_version: bool,
    dry_run: bool,
    commit: Optional[bool],
    tag: Optional[bool],
    sign_tags: Optional[bool],
    tag_name: Optional[str],
    tag_message: Optional[str],
    message: Optional[str],
    commit_args: Optional[str],
) -> None:
    """
    Change the version.

    ARGS may contain any of the following:

    VERSION_PART is the part of the version to increase, e.g. `minor`.
    Valid values include those given in the `--serialize` / `--parse` option.

    FILES are additional file(s) to modify.
    If you want to rewrite only files specified on the command line, use with the
    `--no-configured-files` option.
    """
    setup_logging(verbose)

    logger.info("Starting BumpVersion %s", __version__)

    overrides = get_overrides(
        allow_dirty=allow_dirty,
        current_version=current_version,
        parse=parse,
        serialize=serialize or None,
        search=search,
        replace=replace,
        commit=commit,
        tag=tag,
        sign_tags=sign_tags,
        tag_name=tag_name,
        tag_message=tag_message,
        message=message,
        commit_args=commit_args,
        ignore_missing_files=ignore_missing_files,
        ignore_missing_version=ignore_missing_version,
        regex=regex,
    )

    found_config_file = find_config_file(config_file)
    config = get_configuration(found_config_file, **overrides)
    if args:
        if args[0] not in config.parts.keys():
            raise click.BadArgumentUsage(f"Unknown version component: {args[0]}")
        version_part = args[0]
        files = args[1:]
    else:
        version_part = None
        files = args

    config.allow_dirty = allow_dirty if allow_dirty is not None else config.allow_dirty
    if not config.allow_dirty and config.scm_info.tool:
        config.scm_info.tool.assert_nondirty()

    if no_configured_files:
        config.excluded_paths = list(config.resolved_filemap.keys())

    if files:
        config.add_files(files)
        config.included_paths = files

    logger.dedent()
    do_bump(version_part, new_version, config, found_config_file, dry_run)


@cli.command()
@click.argument("args", nargs=-1, type=str)
@click.option(
    "--config-file",
    metavar="FILE",
    required=False,
    envvar="BUMPVERSION_CONFIG_FILE",
    type=click.Path(exists=True),
    help="Config file to read most of the variables from.",
)
@click.option(
    "-f",
    "--format",
    "format_",
    required=False,
    envvar="BUMPVERSION_FORMAT",
    type=click.Choice(["default", "yaml", "json"], case_sensitive=False),
    default="default",
    help="Config file to read most of the variables from.",
)
@click.option(
    "-i",
    "--increment",
    required=False,
    envvar="BUMPVERSION_INCREMENT",
    type=str,
    help="Increment the version component and add `new_version` to the configuration.",
)
def show(args: List[str], config_file: Optional[str], format_: str, increment: Optional[str]) -> None:
    """
    Show current configuration information.

    ARGS may contain one or more configuration attributes. For example:

    - `bump-my-version show current_version`

    - `bump-my-version show files.0.filename`

    - `bump-my-version show scm_info.branch_name`

    - `bump-my-version show current_version scm_info.distance_to_latest_tag`
    """
    found_config_file = find_config_file(config_file)
    config = get_configuration(found_config_file)

    if not args:
        do_show("all", config=config, format_=format_, increment=increment)
    else:
        do_show(*args, config=config, format_=format_, increment=increment)


@cli.command()
@click.argument("files", nargs=-1, type=str)
@click.option(
    "--config-file",
    metavar="FILE",
    required=False,
    envvar="BUMPVERSION_CONFIG_FILE",
    type=click.Path(exists=True),
    help="Config file to read most of the variables from.",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    required=False,
    envvar="BUMPVERSION_VERBOSE",
    help="Print verbose logging to stderr. Can specify several times for more verbosity.",
)
@click.option(
    "--allow-dirty/--no-allow-dirty",
    default=None,
    required=False,
    envvar="BUMPVERSION_ALLOW_DIRTY",
    help="Don't abort if working directory is dirty, or explicitly abort if dirty.",
)
@click.option(
    "--current-version",
    metavar="VERSION",
    required=False,
    envvar="BUMPVERSION_CURRENT_VERSION",
    help="Version that needs to be updated",
)
@click.option(
    "--new-version",
    metavar="VERSION",
    required=False,
    envvar="BUMPVERSION_NEW_VERSION",
    help="New version that should be in the files. If not specified, it will be None.",
)
@click.option(
    "--parse",
    metavar="REGEX",
    required=False,
    envvar="BUMPVERSION_PARSE",
    help="Regex parsing the version string",
)
@click.option(
    "--serialize",
    metavar="FORMAT",
    multiple=True,
    required=False,
    envvar="BUMPVERSION_SERIALIZE",
    help="How to format what is parsed back to a version",
)
@click.option(
    "--search",
    metavar="SEARCH",
    required=False,
    envvar="BUMPVERSION_SEARCH",
    help="Template for complete string to search",
)
@click.option(
    "--replace",
    metavar="REPLACE",
    required=False,
    envvar="BUMPVERSION_REPLACE",
    help="Template for complete string to replace",
)
@click.option(
    "--regex/--no-regex",
    default=False,
    envvar="BUMPVERSION_REGEX",
    help="Treat the search parameter as a regular expression or explicitly do not treat it as a regular expression.",
)
@click.option(
    "--no-configured-files",
    is_flag=True,
    envvar="BUMPVERSION_NO_CONFIGURED_FILES",
    help=(
        "Only replace the version in files specified on the command line, "
        "ignoring the files from the configuration file."
    ),
)
@click.option(
    "--ignore-missing-version",
    is_flag=True,
    envvar="BUMPVERSION_IGNORE_MISSING_VERSION",
    help="Ignore any Version Not Found errors when searching and replacing in files.",
)
@click.option(
    "--ignore-missing-files",
    is_flag=True,
    envvar="BUMPVERSION_IGNORE_MISSING_FILES",
    help="Ignore any missing files when searching and replacing in files.",
)
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    envvar="BUMPVERSION_DRY_RUN",
    help="Don't write any files, just pretend.",
)
def replace(
    files: list,
    config_file: Optional[str],
    verbose: int,
    allow_dirty: Optional[bool],
    current_version: Optional[str],
    new_version: Optional[str],
    parse: Optional[str],
    serialize: Optional[List[str]],
    search: Optional[str],
    replace: Optional[str],
    regex: bool,
    no_configured_files: bool,
    ignore_missing_version: bool,
    ignore_missing_files: bool,
    dry_run: bool,
) -> None:
    """
    Replace the version in files.

    FILES are additional file(s) to modify.
    If you want to rewrite only files specified on the command line, use with the
    `--no-configured-files` option.
    """
    setup_logging(verbose)

    logger.info("Starting BumpVersion %s", __version__)

    overrides = get_overrides(
        allow_dirty=allow_dirty,
        current_version=current_version,
        new_version=new_version,
        parse=parse,
        serialize=serialize or None,
        commit=False,
        tag=False,
        sign_tags=False,
        tag_name=None,
        tag_message=None,
        message=None,
        commit_args=None,
        ignore_missing_version=ignore_missing_version,
        ignore_missing_files=ignore_missing_files,
        regex=regex,
    )

    found_config_file = find_config_file(config_file)
    config = get_configuration(found_config_file, **overrides)

    config.allow_dirty = allow_dirty if allow_dirty is not None else config.allow_dirty
    if not config.allow_dirty and config.scm_info.tool:
        config.scm_info.tool.assert_nondirty()

    if no_configured_files:
        config.excluded_paths = list(config.resolved_filemap.keys())

    if files:
        config.add_files(files)
        config.included_paths = files

    configured_files = [
        ConfiguredFile(file_cfg, config.version_config, search, replace) for file_cfg in config.files_to_modify
    ]

    version = config.version_config.parse(config.current_version)
    if new_version:
        next_version = config.version_config.parse(new_version)
    else:
        next_version = None

    ctx = get_context(config, version, next_version)

    modify_files(configured_files, version, next_version, ctx, dry_run)


@cli.command()
@click.option(
    "--prompt/--no-prompt",
    default=True,
    help="Ask the user questions about the configuration.",
)
@click.option(
    "--destination",
    default="stdout",
    help="Where to write the sample configuration.",
    type=click.Choice(["stdout", ".bumpversion.toml", "pyproject.toml"]),
)
def sample_config(prompt: bool, destination: str) -> None:
    """Print a sample configuration file."""
    if prompt:
        destination = questionary.select(
            "Destination", choices=["stdout", ".bumpversion.toml", "pyproject.toml"], default=destination
        ).ask()

    destination_config = create_configuration(destination, prompt)

    if destination == "stdout":
        print_info(dumps(destination_config))
    else:
        Path(destination).write_text(dumps(destination_config), encoding="utf-8")


@cli.command()
@click.argument("version", nargs=1, type=str, required=False, default="")
@click.option(
    "--config-file",
    metavar="FILE",
    required=False,
    envvar="BUMPVERSION_CONFIG_FILE",
    type=click.Path(exists=True),
    help="Config file to read most of the variables from.",
)
@click.option("--ascii", is_flag=True, help="Use ASCII characters only.")
@click.option(
    "-v",
    "--verbose",
    count=True,
    required=False,
    envvar="BUMPVERSION_VERBOSE",
    help="Print verbose logging to stderr. Can specify several times for more verbosity.",
)
def show_bump(version: str, config_file: Optional[str], ascii: bool, verbose: int) -> None:
    """Show the possible versions resulting from the bump subcommand."""
    setup_logging(verbose)
    found_config_file = find_config_file(config_file)
    config = get_configuration(found_config_file)
    if not version:
        version = config.current_version
    box_style = "ascii" if ascii else "light"
    visualize(config=config, version_str=version, box_style=box_style)

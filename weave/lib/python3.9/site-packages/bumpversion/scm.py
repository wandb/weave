"""Version control system management."""

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, MutableMapping, Optional, Type, Union

from bumpversion.ui import get_indented_logger
from bumpversion.utils import extract_regex_flags, format_and_raise_error, run_command

if TYPE_CHECKING:  # pragma: no-coverage
    from bumpversion.config import Config

from bumpversion.exceptions import DirtyWorkingDirectoryError, SignedTagsError

logger = get_indented_logger(__name__)


@dataclass
class SCMInfo:
    """Information about the current source code manager and state."""

    tool: Optional[Type["SourceCodeManager"]] = None
    commit_sha: Optional[str] = None
    distance_to_latest_tag: int = 0
    current_version: Optional[str] = None
    current_tag: Optional[str] = None
    branch_name: Optional[str] = None
    short_branch_name: Optional[str] = None
    repository_root: Optional[Path] = None
    dirty: Optional[bool] = None

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        tool_name = self.tool.__name__ if self.tool else "No SCM tool"
        return (
            f"SCMInfo(tool={tool_name}, "
            f"commit_sha={self.commit_sha}, "
            f"distance_to_latest_tag={self.distance_to_latest_tag}, "
            f"current_version={self.current_version}, "
            f"current_tag={self.current_tag}, "
            f"branch_name={self.branch_name}, "
            f"short_branch_name={self.short_branch_name}, "
            f"repository_root={self.repository_root}, "
            f"dirty={self.dirty})"
        )

    def path_in_repo(self, path: Union[Path, str]) -> bool:
        """Return whether a path is inside this repository."""
        if self.repository_root is None:
            return True
        elif not Path(path).is_absolute():
            return True

        return str(path).startswith(str(self.repository_root))


class SourceCodeManager:
    """Base class for version control systems."""

    _TEST_USABLE_COMMAND: ClassVar[List[str]] = []
    _COMMIT_COMMAND: ClassVar[List[str]] = []
    _ALL_TAGS_COMMAND: ClassVar[List[str]] = []

    @classmethod
    def commit(cls, message: str, current_version: str, new_version: str, extra_args: Optional[list] = None) -> None:
        """Commit the changes."""
        extra_args = extra_args or []
        if not current_version:
            logger.warning("No current version given, using an empty string.")
            current_version = ""
        if not new_version:
            logger.warning("No new version given, using an empty string.")
            new_version = ""

        with NamedTemporaryFile("wb", delete=False) as f:
            f.write(message.encode("utf-8"))

        env = os.environ.copy()
        env["HGENCODING"] = "utf-8"
        env["BUMPVERSION_CURRENT_VERSION"] = current_version
        env["BUMPVERSION_NEW_VERSION"] = new_version

        try:
            cmd = [*cls._COMMIT_COMMAND, f.name, *extra_args]
            run_command(cmd, env=env)
        except (subprocess.CalledProcessError, TypeError) as exc:  # pragma: no-coverage
            cls.format_and_raise_error(exc)
        finally:
            os.unlink(f.name)

    @classmethod
    def format_and_raise_error(cls, exc: Union[TypeError, subprocess.CalledProcessError]) -> None:
        """Format the error message from an exception and re-raise it as a BumpVersionError."""
        format_and_raise_error(exc)

    @classmethod
    def is_usable(cls) -> bool:
        """Is the VCS implementation usable."""
        try:
            result = run_command(cls._TEST_USABLE_COMMAND)
            return result.returncode == 0
        except (FileNotFoundError, PermissionError, NotADirectoryError, subprocess.CalledProcessError):
            return False

    @classmethod
    def assert_nondirty(cls) -> None:
        """Assert that the working directory is not dirty."""
        raise NotImplementedError()

    @classmethod
    def latest_tag_info(cls, tag_name: str, parse_pattern: str) -> SCMInfo:
        """Return information about the latest tag."""
        raise NotImplementedError()

    @classmethod
    def add_path(cls, path: Union[str, Path]) -> None:
        """Add a path to the VCS."""
        raise NotImplementedError()

    @classmethod
    def tag(cls, name: str, sign: bool = False, message: Optional[str] = None) -> None:
        """Create a tag of the new_version in VCS."""
        raise NotImplementedError

    @classmethod
    def get_all_tags(cls) -> List[str]:
        """Return all tags in VCS."""
        try:
            result = run_command(cls._ALL_TAGS_COMMAND)
            return result.stdout.splitlines()
        except (FileNotFoundError, PermissionError, NotADirectoryError, subprocess.CalledProcessError):
            return []

    @classmethod
    def get_version_from_tag(cls, tag: str, tag_name: str, parse_pattern: str) -> Optional[str]:
        """Return the version from a tag."""
        version_pattern = parse_pattern.replace("\\\\", "\\")
        version_pattern, regex_flags = extract_regex_flags(version_pattern)
        parts = tag_name.split("{new_version}", maxsplit=1)
        prefix = parts[0]
        suffix = parts[1]
        rep = f"{regex_flags}{re.escape(prefix)}(?P<current_version>{version_pattern}){re.escape(suffix)}"
        tag_regex = re.compile(rep)
        return match["current_version"] if (match := tag_regex.search(tag)) else None

    @classmethod
    def commit_to_scm(
        cls,
        files: List[Union[str, Path]],
        config: "Config",
        context: MutableMapping,
        extra_args: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> None:
        """Commit the files to the source code management system."""
        if not cls.is_usable():
            logger.error("SCM tool '%s' is unusable, unable to commit.", cls.__name__)
            return

        if not config.commit:
            logger.info("Would not commit")
            return

        do_commit = not dry_run
        logger.info(
            "%s %s commit",
            "Preparing" if do_commit else "Would prepare",
            cls.__name__,
        )
        logger.indent()
        for path in files:
            logger.info(
                "%s changes in file '%s' to %s",
                "Adding" if do_commit else "Would add",
                path,
                cls.__name__,
            )

            if do_commit:
                cls.add_path(path)

        commit_message = config.message.format(**context)

        logger.info(
            "%s to %s with message '%s'",
            "Committing" if do_commit else "Would commit",
            cls.__name__,
            commit_message,
        )
        if do_commit:
            cls.commit(
                message=commit_message,
                current_version=context["current_version"],
                new_version=context["new_version"],
                extra_args=extra_args,
            )
        logger.dedent()

    @classmethod
    def tag_in_scm(cls, config: "Config", context: MutableMapping, dry_run: bool = False) -> None:
        """Tag the current commit in the source code management system."""
        if not config.tag:
            logger.info("Would not tag")
            return
        sign_tags = config.sign_tags
        tag_name = config.tag_name.format(**context)
        tag_message = config.tag_message.format(**context)
        existing_tags = cls.get_all_tags()
        do_tag = not dry_run

        if tag_name in existing_tags:
            logger.warning("Tag '%s' already exists. Will not tag.", tag_name)
            return

        logger.info(
            "%s '%s' %s in %s and %s",
            "Tagging" if do_tag else "Would tag",
            tag_name,
            f"with message '{tag_message}'" if tag_message else "without message",
            cls.__name__,
            "signing" if sign_tags else "not signing",
        )
        if do_tag:
            cls.tag(tag_name, sign_tags, tag_message)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f"{self.__class__.__name__}"


class Git(SourceCodeManager):
    """Git implementation."""

    _TEST_USABLE_COMMAND: ClassVar[List[str]] = ["git", "rev-parse", "--git-dir"]
    _COMMIT_COMMAND: ClassVar[List[str]] = ["git", "commit", "-F"]
    _ALL_TAGS_COMMAND: ClassVar[List[str]] = ["git", "tag", "--list"]

    @classmethod
    def assert_nondirty(cls) -> None:
        """Assert that the working directory is not dirty."""
        lines = [
            line.strip()
            for line in run_command(["git", "status", "--porcelain"]).stdout.splitlines()
            if not line.strip().startswith("??")
        ]
        if joined_lines := "\n".join(lines):
            raise DirtyWorkingDirectoryError(f"Git working directory is not clean:\n\n{joined_lines}")

    @classmethod
    def latest_tag_info(cls, tag_name: str, parse_pattern: str) -> SCMInfo:
        """Return information about the latest tag."""
        if not cls.is_usable():
            return SCMInfo()

        info: Dict[str, Any] = {"tool": cls}

        try:
            # git-describe doesn't update the git-index, so we do that
            run_command(["git", "update-index", "--refresh", "-q"])
        except subprocess.CalledProcessError as e:
            logger.debug("Error when running git update-index: %s", e.stderr)

        commit_info = cls._commit_info(parse_pattern, tag_name)
        rev_info = cls._revision_info()
        info.update(commit_info)
        info.update(rev_info)

        return SCMInfo(**info)

    @classmethod
    def _commit_info(cls, parse_pattern: str, tag_name: str) -> dict:
        """
        Get the commit info for the repo.

        Args:
            parse_pattern: The regular expression pattern used to parse the version from the tag.
            tag_name: The tag name format used to locate the latest tag.

        Returns:
            A dictionary containing information about the latest commit.
        """
        tag_pattern = tag_name.replace("{new_version}", "*")
        info = dict.fromkeys(["dirty", "commit_sha", "distance_to_latest_tag", "current_version", "current_tag"])
        info["distance_to_latest_tag"] = 0
        try:
            # get info about the latest tag in git
            git_cmd = [
                "git",
                "describe",
                "--dirty",
                "--tags",
                "--long",
                "--abbrev=40",
                f"--match={tag_pattern}",
            ]
            result = run_command(git_cmd)
            describe_out = result.stdout.strip().split("-")
            if describe_out[-1].strip() == "dirty":
                info["dirty"] = True
                describe_out.pop()
            else:
                info["dirty"] = False

            info["commit_sha"] = describe_out.pop().lstrip("g")
            info["distance_to_latest_tag"] = int(describe_out.pop())
            info["current_tag"] = "-".join(describe_out)
            version = cls.get_version_from_tag("-".join(describe_out), tag_name, parse_pattern)
            info["current_version"] = version or "-".join(describe_out).lstrip("v")
        except subprocess.CalledProcessError as e:
            logger.debug("Error when running git describe: %s", e.stderr)

        return info

    @classmethod
    def _revision_info(cls) -> dict:
        """
        Returns a dictionary containing revision information.

        If an error occurs while running the git command, the dictionary values will be set to None.

        Returns:
            A dictionary with the following keys:
                - branch_name: The name of the current branch.
                - short_branch_name: A 20 lowercase characters of the branch name with special characters removed.
                - repository_root: The root directory of the Git repository.
        """
        info = dict.fromkeys(["branch_name", "short_branch_name", "repository_root"])

        try:
            git_cmd = ["git", "rev-parse", "--show-toplevel", "--abbrev-ref", "HEAD"]
            result = run_command(git_cmd)
            lines = [line.strip() for line in result.stdout.split("\n")]
            repository_root = Path(lines[0])
            branch_name = lines[1]
            short_branch_name = re.sub(r"([^a-zA-Z0-9]*)", "", branch_name).lower()[:20]
            info["branch_name"] = branch_name
            info["short_branch_name"] = short_branch_name
            info["repository_root"] = repository_root
        except subprocess.CalledProcessError as e:
            logger.debug("Error when running git rev-parse: %s", e.stderr)

        return info

    @classmethod
    def add_path(cls, path: Union[str, Path]) -> None:
        """Add a path to the VCS."""
        info = SCMInfo(**cls._revision_info())
        if not info.path_in_repo(path):
            return
        cwd = Path.cwd()
        temp_path = os.path.relpath(path, cwd)
        try:
            run_command(["git", "add", "--update", str(temp_path)])
        except subprocess.CalledProcessError as e:
            format_and_raise_error(e)

    @classmethod
    def tag(cls, name: str, sign: bool = False, message: Optional[str] = None) -> None:
        """
        Create a tag of the new_version in VCS.

        If only name is given, bumpversion uses a lightweight tag.
        Otherwise, it uses an annotated tag.

        Args:
            name: The name of the tag
            sign: True to sign the tag
            message: An optional message to annotate the tag.
        """
        command = ["git", "tag", name]
        if sign:
            command += ["--sign"]
        if message:
            command += ["--message", message]
        run_command(command)


class Mercurial(SourceCodeManager):
    """Mercurial implementation."""

    _TEST_USABLE_COMMAND: ClassVar[List[str]] = ["hg", "root"]
    _COMMIT_COMMAND: ClassVar[List[str]] = ["hg", "commit", "--logfile"]
    _ALL_TAGS_COMMAND: ClassVar[List[str]] = ["hg", "log", '--rev="tag()"', '--template="{tags}\n"']

    @classmethod
    def latest_tag_info(cls, tag_name: str, parse_pattern: str) -> SCMInfo:
        """Return information about the latest tag."""
        current_version = None
        re_pattern = tag_name.replace("{new_version}", ".*")
        result = run_command(["hg", "log", "-r", f"tag('re:{re_pattern}')", "--template", "{latesttag}\n"])
        result.check_returncode()
        if result.stdout:
            tag_string = result.stdout.splitlines(keepends=False)[-1]
            current_version = cls.get_version_from_tag(tag_string, tag_name, parse_pattern)
        else:
            logger.debug("No tags found")
        is_dirty = len(run_command(["hg", "status", "-mard"]).stdout) != 0
        return SCMInfo(tool=cls, current_version=current_version, dirty=is_dirty)

    @classmethod
    def assert_nondirty(cls) -> None:
        """Assert that the working directory is clean."""
        lines = [
            line.strip()
            for line in run_command(["hg", "status", "-mard"]).stdout.splitlines()
            if not line.strip().startswith("??")
        ]

        if lines:
            joined_lines = "\n".join(lines)
            raise DirtyWorkingDirectoryError(f"Mercurial working directory is not clean:\n{joined_lines}")

    @classmethod
    def add_path(cls, path: Union[str, Path]) -> None:
        """Add a path to the VCS."""
        pass

    @classmethod
    def tag(cls, name: str, sign: bool = False, message: Optional[str] = None) -> None:
        """
        Create a tag of the new_version in VCS.

        If only name is given, bumpversion uses a lightweight tag.
        Otherwise, it uses an annotated tag.

        Args:
            name: The name of the tag
            sign: True to sign the tag
            message: A optional message to annotate the tag.

        Raises:
            SignedTagsError: If ``sign`` is ``True``
        """
        command = ["hg", "tag", name]
        if sign:
            raise SignedTagsError("Mercurial does not support signed tags.")
        if message:
            command += ["--message", message]
        run_command(command)


def get_scm_info(tag_name: str, parse_pattern: str) -> SCMInfo:
    """Return a dict with the latest source code management info."""
    if Git.is_usable():
        return Git.latest_tag_info(tag_name, parse_pattern)
    elif Mercurial.is_usable():
        return Mercurial.latest_tag_info(tag_name, parse_pattern)
    else:
        return SCMInfo()

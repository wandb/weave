"""Utilities for handling command aliases."""

from typing import List, Optional

import rich_click as click
from click import Context
from rich_click.rich_group import RichGroup

from bumpversion.ui import print_warning


class AliasedGroup(RichGroup):
    """
    This following example implements a subclass of Group that accepts a prefix for a command.

    If there were a command called ``push``, it would accept ``pus`` as an alias (so long as it was unique)
    """

    def get_command(self, ctx: Context, cmd_name: str) -> Optional[click.Command]:  # type: ignore[return]
        """Given a context and a command name, this returns a Command object if it exists or returns None."""
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx) if x.startswith(cmd_name)]
        if not matches:
            args = [cmd_name, *ctx.args]
            new_ctx = self.make_context(ctx.info_name, args, parent=ctx)
            return click.Group.get_command(self, new_ctx, "bump")
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail(f"Too many matches: {', '.join(sorted(matches))}")

    def resolve_command(self, ctx: Context, args: List[str]) -> tuple:
        """Find the command and make sure the full command name is returned."""
        # always return the full command name
        original_args = args[:]
        _, cmd, args = super().resolve_command(ctx, args)

        if cmd.name == "bump" and args != original_args:
            if "bump" in original_args:
                original_args.remove("bump")
            else:
                print_warning(
                    "Calling bumpversion without a subcommand is deprecated. "
                    "Please use `bump-my-version bump` instead"
                )
            return cmd.name, cmd, original_args
        return cmd.name, cmd, args

import argparse
from typing import Optional

import weave
from weave.flow.rules import CallFunctionAction, OnlineCallRule
from weave.trace.refs import OpRef
from weave.trace_server.trace_server_interface import CallsFilter

from .was_polite_judge import WasPolite


def initialize_rules(project_id: str) -> None:
    """
    Initialize rules for the given project.

    Args:
        project_id (str): The ID of the project to initialize rules for.
    """
    client = weave.init(project_id=project_id)
    entity, project = client._project_id().split("/")

    rule = OnlineCallRule(
        when=CallsFilter(
            op_names=[OpRef(
                entity=entity,
                project=project,
                name="openai.chat.completions.create",
                _digest="*"
            ).uri()]
        ),
        action=CallFunctionAction(fn=WasPolite())
    )

    # How to disable a rule?
    weave.publish(rule)

    pass

def main(args: Optional[argparse.Namespace] = None) -> None:
    """
    Main function to parse command line arguments and run initialize_rules.

    Args:
        args (Optional[argparse.Namespace]): Parsed command line arguments.
            If None, arguments will be parsed from sys.argv.
    """
    if args is None:
        parser = argparse.ArgumentParser(description="Initialize rules for a project.")
        parser.add_argument("project_id", type=str, help="The ID of the project to initialize rules for.")
        args = parser.parse_args()

    initialize_rules(args.project_id)

if __name__ == "__main__":
    main()

from collections.abc import Collection
import libcst
from fixit import Invalid, LintRule, Valid
from libcst.metadata import QualifiedNameProvider


class ClientCallsRule(LintRule):
    """
    Convert client.calls() to client.get_calls().
    
    This rule matches function calls and checks if they are calling the 'calls' method
    on a 'client' object, then suggests replacing it with 'get_calls'.
    """
    VALID = [Valid("client.get_calls")]
    INVALID = [Invalid("client.calls")]
    
    def visit_Call(self, node: libcst.Call) -> None:
        if (
            isinstance(node.func, libcst.Attribute)
            and isinstance(node.func.value, libcst.Name)
            and node.func.value.value == "client"
            and node.func.attr.value == "calls"
        ):
            new_call = node.with_changes(
                func=node.func.with_changes(
                    attr=libcst.Name("get_calls")
                )
            )
            self.report(
                node,
                "Use client.get_calls() instead of client.calls()",
                replacement=new_call,
            )
            
class ClientCallRule(LintRule):
    """
    Convert client.call() to client.get_call().
    
    This rule matches function calls and checks if they are calling the 'call' method
    on a 'client' object, then suggests replacing it with 'get_call'.
    """
    VALID = [Valid("client.get_call")]
    INVALID = [Invalid("client.call")]

    def visit_Call(self, node: libcst.Call) -> None:
        if (
            isinstance(node.func, libcst.Attribute)
            and isinstance(node.func.value, libcst.Name)
            and node.func.value.value == "client"
            and node.func.attr.value == "call"
        ):
            new_call = node.with_changes(
                func=node.func.with_changes(
                    attr=libcst.Name("get_call")
                )
            )
            self.report(
                node,
                "Use client.get_call() instead of client.call()",
                replacement=new_call,
            )
            

class ClientFeedbackRule(LintRule):
    """
    Convert client.feedback() to client.get_feedback().
    
    This rule matches function calls and checks if they are calling the 'feedback' method
    on a 'client' object, then suggests replacing it with 'get_feedback'.
    """
    VALID = [Valid("client.get_feedback")]
    INVALID = [Invalid("client.feedback")]
    
    def visit_Call(self, node: libcst.Call) -> None:
        if (
            isinstance(node.func, libcst.Attribute)
            and isinstance(node.func.value, libcst.Name)
            and node.func.value.value == "client"
            and node.func.attr.value == "feedback"
        ):
            new_call = node.with_changes(
                func=node.func.with_changes(
                    attr=libcst.Name("get_feedback")
                )
            )
            self.report(
                node,
                "Use client.get_feedback() instead of client.feedback()",
                replacement=new_call,
            )


class ReplaceFileWithContentRule(LintRule):
    """
    Replaces instantiations of the deprecated `File` class with `Content.from_path`.

    This rule identifies calls to `File(path, ...)` and suggests replacing them
    with the new `Content.from_path(path, ...)` API.

    Note: This rule handles the call-site replacement but does not automatically
    add the required `from weave.type_wrappers.Content.content import Content`
    import statement. After applying this fix, you may need to add the
    import manually or run an import-organizing tool.
    """

    # Use the QualifiedNameProvider to ensure we only match the intended `File` class.
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)

    VALID = [
        Valid(
            """
            from weave.type_wrappers.Content.content import Content
            # This is already using the new API, so no change is needed.
            c = Content.from_path("foo.txt")
            """
        ),
        Valid(
            """
            # A different class named File should be ignored.
            class File:
                pass
            f = File()
            """
        ),
    ]
    INVALID = [
        Invalid(
            """
            from weave.type_handlers.File import File
            f = File("foo.txt")
            """,
            expected_replacement="""
            from weave.type_handlers.File import File
            f = Content.from_path("foo.txt")
            """,
        ),
        Invalid(
            """
            from weave.type_handlers.File import File
            from pathlib import Path
            f = File(Path("data.csv"), mimetype="text/csv")
            """,
            expected_replacement="""
            from weave.type_handlers.File import File
            from pathlib import Path
            f = Content.from_path(Path("data.csv"), mimetype="text/csv")
            """,
        ),
    ]

    def visit_Call(self, node: libcst.Call) -> None:
        """Visit a Call node and check if it's a `File` instantiation."""
        # Get all possible fully qualified names for the function being called.
        q_names = self.get_metadata(QualifiedNameProvider, node.func)

        # Safely handle cases where metadata cannot be resolved.
        if not isinstance(q_names, Collection):
            return

        # Check if any of the names match the deprecated class we want to replace.
        is_deprecated_file = any(
            name.name == "weave.type_handlers.File.File" for name in q_names
        )

        if is_deprecated_file:
            # Construct the new function call: `Content.from_path(...)`
            # 1. Create the base object: `Content`
            # 2. Create the attribute to access: `.from_path`
            new_func = libcst.Attribute(
                value=libcst.Name("Content"), attr=libcst.Name("from_path")
            )

            # 3. Create the new Call node, replacing the function but keeping args.
            replacement_node = node.with_changes(func=new_func)

            # Report the violation and provide the fix.
            self.report(
                node,
                "The `File` class is deprecated. Use `Content.from_path` instead. "
                "You may need to add 'from weave import Content'.",
                replacement=replacement_node,
            )

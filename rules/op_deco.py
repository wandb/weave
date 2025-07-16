import libcst
from fixit import InvalidTestCase, LintRule, ValidTestCase


class OpDecoRule(LintRule):
    """
    This rule converts @weave.op() to @weave.op.

    This is a stylistic rule that we prefer to use the decorator without parentheses.
    """
    VALID = [ValidTestCase("@weave.op")]
    INVALID = [InvalidTestCase("@weave.op()")]

    def visit_Decorator(self, node: libcst.Decorator) -> None:
        if (
            isinstance(node.decorator, libcst.Call)
            and isinstance(attr := node.decorator.func, libcst.Attribute)
            and isinstance(name := attr.value, libcst.Name)
            and name.value == "weave"
            and node.decorator.args == ()
        ):
            op_without_parens = libcst.Decorator(decorator=attr)
            self.report(
                node,
                "Prefer @weave.op over @weave.op()",
                replacement=op_without_parens,
            )

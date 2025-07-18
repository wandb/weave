import libcst
from fixit import InvalidTestCase, LintRule, ValidTestCase


class ClientCallsRule(LintRule):
    """
    Convert client.calls() to client.get_calls().
    
    This rule matches function calls and checks if they are calling the 'calls' method
    on a 'client' object, then suggests replacing it with 'get_calls'.
    """
    VALID = [ValidTestCase("client.get_calls")]
    INVALID = [InvalidTestCase("client.calls")]
    
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
    VALID = [ValidTestCase("client.get_call")]
    INVALID = [InvalidTestCase("client.call")]
    
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
    VALID = [ValidTestCase("client.get_feedback")]
    INVALID = [InvalidTestCase("client.feedback")]
    
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
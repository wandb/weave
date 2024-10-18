from weave.flow.rules import Function


class WasPolite(Function):
    def invoke(self, call):
        return isinstance(call.output, str) and "!" not in call.output
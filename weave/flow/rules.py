import pydantic

import weave

# from weave.integrations.litellm import litellm
from weave.trace.weave_client import Call
from weave.trace_server.trace_server_interface import CallsFilter


class Function(weave.Object):
    @weave.op()
    def invoke(self, call: Call):
        pass


# class LLMFunction(Function):
#     # prompt is something that has a .format() method. MessagesPrompt
#     # is one that returns a list of chat messages.
#     prompt: str
#     response_format: pydantic.BaseModel
#     model_name: str
#     temperature: float
    
#     def invoke(self, call):
#         # should we receive call or input?
#         messages = this.prompt.format(call.as_flat_dict())
#         return litellm.chat.completions.parse(
#             messages=messages,
#             model_name=model_name,
#             temperature=temperature,
#             response_format=self.response_format)

class CallFunctionAction(pydantic.BaseModel):
    fn: Function

type OnlineRuleAction = CallFunctionAction

class OnlineCallRule(weave.Object):
    # This should match our standard call filter or CallQuery probably
    when: CallsFilter
    # We can have a bunch of these in the future
    action: OnlineRuleAction

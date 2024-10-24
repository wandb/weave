import litellm
from typing import Any, List, Dict
import json
from weave.trace_server import trace_server_interface as tsi
from weave.trace import weave_init as w
import weave_query as weave
      

def call_llm(project_id: str, api_key: str, model_name: str, messages: List[Dict[str, Any]]) -> tsi.CallsLLMRes:

    w.init_weave(project_id)

    @weave.op()
    def llm_complete(api_key: str, model_name: str, messages: List[Dict[str, Any]]) -> tsi.CallsLLMRes:
        litellm.api_key = api_key
        res = litellm.completion(messages=messages, model=model_name)
        return tsi.CallsLLMRes(response=res.model_dump())
    
    return llm_complete(api_key, model_name, messages)
        
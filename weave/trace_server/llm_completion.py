import litellm
from typing import Any, List
import json
from weave.trace_server import trace_server_interface as tsi
        

def call_llm(req: tsi.CallsLLMReq) -> tsi.CallsLLMRes:
    if req.api_key:
        litellm.api_key = req.api_key
    msg = []
    for s in req.messages:
        json_s = f"{{{s}}}"
        msg.append(json.loads(json_s))
    res = litellm.completion(messages=msg, model=req.model_name)
    return res
    
        
import litellm
from typing import Any, List, Dict
import json
from weave.trace_server import trace_server_interface as tsi
        

def call_llm(api_key: str, model_name: str, messages: List[Dict[str, Any]]) -> tsi.CallsLLMRes:
    litellm.api_key = api_key
    try:
        res = litellm.completion(messages=messages, model=model_name)
        return tsi.CallsLLMRes(response=res.model_dump())
    except Exception as e:
        return tsi.CallsLLMRes(response={"error": e.message})
    
        
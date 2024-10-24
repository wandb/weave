import litellm
from typing import Any, List, Dict
import json
from weave.trace_server import trace_server_interface as tsi
        

def lite_llm_completion(api_key: str, model_name: str, inputs: tsi.ExecuteLLMCompletionRequestInputs) -> tsi.ExecuteLLMCompletionRes:
    try:
        res = litellm.completion(**inputs.model_dump(), model=model_name, api_key=api_key)
        return tsi.ExecuteLLMCompletionRes(response=res.model_dump())
    except Exception as e:
        return tsi.ExecuteLLMCompletionRes(response={"error": e.message})
    
        
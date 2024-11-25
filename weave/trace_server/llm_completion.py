from weave.trace_server import trace_server_interface as tsi


def lite_llm_completion(
    api_key: str, inputs: tsi.CompletionsCreateRequestInputs
) -> tsi.CompletionsCreateRes:
    import litellm

    # This allows us to drop params that are not supported by the LLM provider
    litellm.drop_params = True
    try:
        res = litellm.completion(
            **inputs.model_dump(exclude_none=True), api_key=api_key
        )
        return tsi.CompletionsCreateRes(response=res.model_dump())
    except Exception as e:
        return tsi.CompletionsCreateRes(response={"error": str(e)})

from typing import TYPE_CHECKING, Any, Optional

import weave
from weave.trace.weave_client import Call

if TYPE_CHECKING:
    from botocore.client import BaseClient


def bedrock_on_finish_converse(
    call: Call, output: Any, exception: Optional[BaseException]
) -> None:
    print(call, type(call))
    model_name = call.inputs["modelId"]
    usage = {model_name: {"requests": 1}}
    summary_update = {"usage": usage}
    if output:
        tokens_metrics = {
            "prompt_tokens": output["usage"]["inputTokens"],
            "completion_tokens": output["usage"]["outputTokens"],
            "total_tokens": output["usage"]["totalTokens"],
        }
        usage[model_name].update(tokens_metrics)
    if call.summary is not None:
        call.summary.update(summary_update)


def bedrock_on_finish_invoke(
    call: Call, output: Any, exception: Optional[BaseException]
) -> None:
    model_name = call.inputs["modelId"]
    usage = {model_name: {"requests": 1}}
    summary_update = {"usage": usage}

    if output and "ResponseMetadata" in output:
        headers = output["ResponseMetadata"]["HTTPHeaders"]
        prompt_tokens = int(headers.get("x-amzn-bedrock-input-token-count", 0))
        completion_tokens = int(headers.get("x-amzn-bedrock-output-token-count", 0))
        total_tokens = prompt_tokens + completion_tokens

        tokens_metrics = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        usage[model_name].update(tokens_metrics)


def postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    return inputs.get("kwargs", {})


def _patch_converse(bedrock_client: "BaseClient") -> None:
    print("patching converse API")
    op = weave.op(
        bedrock_client.converse,
        name="BedrockRuntime.converse",
        postprocess_inputs=postprocess_inputs,
    )
    op._set_on_finish_handler(bedrock_on_finish_converse)
    bedrock_client.converse = op


def _patch_invoke(bedrock_client: "BaseClient") -> None:
    print("patching invoke API")
    op = weave.op(
        bedrock_client.invoke_model,
        name="BedrockRuntime.invoke",
        postprocess_inputs=postprocess_inputs,
    )
    op._set_on_finish_handler(bedrock_on_finish_invoke)
    bedrock_client.invoke_model = op


def patch_client(bedrock_client: "BaseClient") -> None:
    _patch_converse(bedrock_client)
    _patch_invoke(bedrock_client)

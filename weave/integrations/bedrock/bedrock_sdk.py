import copy
import io
import json
from typing import TYPE_CHECKING, Any, Callable, Optional

import weave
from weave.trace.op import _add_accumulator, _IteratorWrapper
from weave.trace.weave_client import Call

if TYPE_CHECKING:
    from botocore.client import BaseClient


def bedrock_on_finish_converse(
    call: Call, output: Any, exception: Optional[BaseException]
) -> None:
    model_name = str(call.inputs["modelId"])  # get the ref
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
    model_name = str(call.inputs["modelId"])
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
    if call.summary is not None:
        call.summary.update(summary_update)


def postprocess_inputs_converse(inputs: dict[str, Any]) -> dict[str, Any]:
    return inputs.get("kwargs", {})


def postprocess_inputs_apply_guardrail(inputs: dict[str, Any]) -> dict[str, Any]:
    return inputs.get("kwargs", {})


def postprocess_inputs_invoke(inputs: dict[str, Any]) -> dict[str, Any]:
    exploded_kwargs = inputs.get("kwargs", {})
    if "body" in exploded_kwargs:
        exploded_kwargs["body"] = json.loads(exploded_kwargs["body"])
    return exploded_kwargs


def postprocess_output_invoke(outputs: dict[str, Any]) -> dict[str, Any]:
    """Process the outputs for logging without affecting the original response."""
    if "body" in outputs:
        # Get the original body
        body = outputs["body"]

        # Read the content
        body_content = body.read()

        # Create a copy of the outputs for logging
        outputs_copy = {k: copy.deepcopy(v) for k, v in outputs.items() if k != "body"}

        try:
            # Try to parse as JSON for the logged copy
            body_str = body_content.decode("utf-8")
            outputs_copy["body"] = json.loads(body_str)
        except (UnicodeDecodeError, json.JSONDecodeError):
            # If we can't decode or parse, just use the raw content
            outputs_copy["body"] = {"raw_content": str(body_content)}

        # Create a BytesIO object from the content for the original response
        outputs["body"] = io.BytesIO(body_content)

        return outputs_copy
    return outputs


def _patch_converse(bedrock_client: "BaseClient") -> None:
    op = weave.op(
        bedrock_client.converse,
        name="BedrockRuntime.converse",
        postprocess_inputs=postprocess_inputs_converse,
    )
    op._set_on_finish_handler(bedrock_on_finish_converse)
    bedrock_client.converse = op


def _patch_invoke(bedrock_client: "BaseClient") -> None:
    op = weave.op(
        bedrock_client.invoke_model,
        name="BedrockRuntime.invoke",
        postprocess_inputs=postprocess_inputs_invoke,
        postprocess_output=postprocess_output_invoke,
    )
    op._set_on_finish_handler(bedrock_on_finish_invoke)
    bedrock_client.invoke_model = op


def _patch_apply_guardrail(bedrock_client: "BaseClient") -> None:
    op = weave.op(
        bedrock_client.apply_guardrail,
        name="BedrockRuntime.apply_guardrail",
        postprocess_inputs=postprocess_inputs_apply_guardrail,
    )
    bedrock_client.apply_guardrail = op


def bedrock_stream_accumulator(
    acc: Optional[dict],
    value: dict,
) -> dict:
    """Accumulates streaming events into a final response dictionary."""
    if acc is None:
        acc = {
            "role": None,
            "content": "",
            "stop_reason": None,
            "usage": {
                "inputTokens": 0,
                "outputTokens": 0,
                "totalTokens": 0,
            },
            "latency_ms": None,
        }

    # Handle 'messageStart' event
    if "messageStart" in value:
        acc["role"] = value["messageStart"]["role"]

    # Handle 'contentBlockDelta' event
    if "contentBlockDelta" in value:
        acc["content"] += value["contentBlockDelta"]["delta"]["text"]

    # Handle 'messageStop' event
    if "messageStop" in value:
        acc["stop_reason"] = value["messageStop"]["stopReason"]

    # Handle 'metadata' event
    if "metadata" in value:
        metadata = value["metadata"]
        if "usage" in metadata:
            acc["usage"]["inputTokens"] = metadata["usage"].get("inputTokens", 0)
            acc["usage"]["outputTokens"] = metadata["usage"].get("outputTokens", 0)
            acc["usage"]["totalTokens"] = metadata["usage"].get("totalTokens", 0)
        if "metrics" in metadata:
            acc["latency_ms"] = metadata["metrics"].get("latencyMs", 0)

    return acc


def create_stream_wrapper(
    name: str,
) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op(postprocess_inputs=postprocess_inputs_converse)(fn)
        op.name = name  # type: ignore
        op._set_on_finish_handler(bedrock_on_finish_converse)

        class BedrockIteratorWrapper(_IteratorWrapper):
            def get(self, key: str, default: Any = None) -> Any:
                """Delegate 'get' method to the response object."""
                if key == "stream":
                    if hasattr(self._iterator_or_ctx_manager, "get"):
                        self._iterator_or_ctx_manager = (
                            self._iterator_or_ctx_manager.get("stream")
                        )
                    return self

        return _add_accumulator(
            op,
            make_accumulator=lambda _: bedrock_stream_accumulator,
            should_accumulate=lambda _: True,
            iterator_wrapper=BedrockIteratorWrapper,
        )

    return wrapper


def _patch_converse_stream(bedrock_client: "BaseClient") -> None:
    """Patches the converse_stream method to handle streaming."""
    op = create_stream_wrapper("BedrockRuntime.converse_stream")(
        bedrock_client.converse_stream
    )
    bedrock_client.converse_stream = op


def patch_client(bedrock_client: "BaseClient") -> None:
    _patch_converse(bedrock_client)
    _patch_invoke(bedrock_client)
    _patch_apply_guardrail(bedrock_client)
    _patch_converse_stream(bedrock_client)

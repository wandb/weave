from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Literal

import requests
from pydantic import ValidationError

from weave.chat.stream import ChatCompletionChunkStream
from weave.chat.types._models import (
    NOT_GIVEN,
    NotGiven,
)
from weave.chat.types.chat_completion import ChatCompletion
from weave.chat.types.chat_completion_stream_options_param import (
    ChatCompletionStreamOptionsParam,
)
from weave.trace.env import weave_trace_server_url
from weave.trace.op import op
from weave.trace_server.constants import COMPLETIONS_CREATE_OP_NAME, INFERENCE_HOST
from weave.wandb_interface.wandb_api import get_wandb_api_context

if TYPE_CHECKING:
    from weave.trace.weave_client import WeaveClient

Endpoint = Literal["playground", "inference"]


# TODO: We remove these to align with OpenAI's API, but maybe they would be useful to keep?
IGNORE_ARGS = ("self", "endpoint", "track_llm_call")


def postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Update arguments for closer alignment with OpenAI API."""
    kwargs = inputs.get("kwargs", {})
    return {
        k: v for k, v in kwargs.items() if k not in IGNORE_ARGS and v is not NOT_GIVEN
    }


class Completions:
    def __init__(self, client: WeaveClient):
        self._client = client

    def create(
        self,
        *,
        endpoint: Endpoint = "playground",
        track_llm_call: bool = True,
        messages: Iterable,
        model: str,
        frequency_penalty: float | None | NotGiven = NOT_GIVEN,
        max_tokens: int | None | NotGiven = NOT_GIVEN,
        n: int | None | NotGiven = NOT_GIVEN,
        presence_penalty: float | None | NotGiven = NOT_GIVEN,
        stream: Literal[False] | Literal[True] | None | NotGiven = NOT_GIVEN,
        stream_options: ChatCompletionStreamOptionsParam | None | NotGiven = NOT_GIVEN,
        temperature: float | None | NotGiven = NOT_GIVEN,
        top_p: float | None | NotGiven = NOT_GIVEN,
        # messages: Iterable[ChatCompletionMessageParam],
        # model: Union[str, ChatModel],
        # audio: Optional[ChatCompletionAudioParam] | NotGiven = NOT_GIVEN,
        # frequency_penalty: Optional[float] | NotGiven = NOT_GIVEN,
        # function_call: completion_create_params.FunctionCall | NotGiven = NOT_GIVEN,
        # functions: Iterable[completion_create_params.Function] | NotGiven = NOT_GIVEN,
        # logit_bias: Optional[Dict[str, int]] | NotGiven = NOT_GIVEN,
        # logprobs: Optional[bool] | NotGiven = NOT_GIVEN,
        # max_completion_tokens: Optional[int] | NotGiven = NOT_GIVEN,
        # max_tokens: Optional[int] | NotGiven = NOT_GIVEN,
        # metadata: Optional[Metadata] | NotGiven = NOT_GIVEN,
        # modalities: Optional[List[Literal["text", "audio"]]] | NotGiven = NOT_GIVEN,
        # parallel_tool_calls: bool | NotGiven = NOT_GIVEN,
        # prediction: Optional[ChatCompletionPredictionContentParam] | NotGiven = NOT_GIVEN,
        # reasoning_effort: Optional[ReasoningEffort] | NotGiven = NOT_GIVEN,
        # response_format: completion_create_params.ResponseFormat | NotGiven = NOT_GIVEN,
        # seed: Optional[int] | NotGiven = NOT_GIVEN,
        # service_tier: Optional[Literal["auto", "default", "flex"]] | NotGiven = NOT_GIVEN,
        # stop: Union[Optional[str], List[str], None] | NotGiven = NOT_GIVEN,
        # store: Optional[bool] | NotGiven = NOT_GIVEN,
        # tool_choice: ChatCompletionToolChoiceOptionParam | NotGiven = NOT_GIVEN,
        # tools: Iterable[ChatCompletionToolParam] | NotGiven = NOT_GIVEN,
        # top_logprobs: Optional[int] | NotGiven = NOT_GIVEN,
        # user: str | NotGiven = NOT_GIVEN,
        # web_search_options: completion_create_params.WebSearchOptions | NotGiven = NOT_GIVEN,
        # # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # # The extra values given here take precedence over values defined on the client or passed to this method.
        # extra_headers: Headers | None = None,
        # extra_query: Query | None = None,
        # extra_body: Body | None = None,
        # timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN,
    ) -> ChatCompletion | ChatCompletionChunkStream:
        """
        Creates a completion for the provided prompt and parameters.

        Args:

          endpoint: "playground" to use Weave's playground API, "inference" to use the inference service API.

          track_llm_call: Whether to track the LLM call.

          messages: A list of messages comprising the conversation so far.

          model: ID of the model to use.

          frequency_penalty: Number between -2.0 and 2.0. Positive values penalize new tokens based on their
              existing frequency in the text so far, decreasing the model's likelihood to
              repeat the same line verbatim.

              [See more information about frequency and presence penalties.](https://platform.openai.com/docs/guides/text-generation)

          max_tokens: The maximum number of [tokens](/tokenizer) that can be generated in the
              completion.

              The token count of your prompt plus `max_tokens` cannot exceed the model's
              context length.
              [Example Python code](https://cookbook.openai.com/examples/how_to_count_tokens_with_tiktoken)
              for counting tokens.

          n: How many completions to generate for each prompt.

              **Note:** Because this parameter generates many completions, it can quickly
              consume your token quota. Use carefully and ensure that you have reasonable
              settings for `max_tokens` and `stop`.

          presence_penalty: Number between -2.0 and 2.0. Positive values penalize new tokens based on
              whether they appear in the text so far, increasing the model's likelihood to
              talk about new topics.

              [See more information about frequency and presence penalties.](https://platform.openai.com/docs/guides/text-generation)

          stream: Whether to stream back partial progress.

          stream_options: Options for streaming response. Only set this when you set `stream: true`.

          temperature: What sampling temperature to use, between 0 and 2. Higher values like 0.8 will
              make the output more random, while lower values like 0.2 will make it more
              focused and deterministic.

              We generally recommend altering this or `top_p` but not both.

          top_p: An alternative to sampling with temperature, called nucleus sampling, where the
              model considers the results of the tokens with top_p probability mass. So 0.1
              means only the tokens comprising the top 10% probability mass are considered.

              We generally recommend altering this or `temperature` but not both.
        """
        kwargs = {
            "endpoint": endpoint,
            "messages": messages,
            "model": model,
            "frequency_penalty": frequency_penalty,
            "max_tokens": max_tokens,
            "n": n,
            "presence_penalty": presence_penalty,
            "stream": stream,
            "stream_options": stream_options,
            "temperature": temperature,
            "top_p": top_p,
        }
        return (
            self._create_op(**kwargs)
            if track_llm_call
            else self._create_non_op(**kwargs)
        )

    @op(name=COMPLETIONS_CREATE_OP_NAME, postprocess_inputs=postprocess_inputs)
    def _create_op(self, **kwargs: Any) -> ChatCompletion | ChatCompletionChunkStream:
        return self._create_non_op(**kwargs)

    def _create_non_op(
        self,
        **kwargs: Any,
    ) -> ChatCompletion | ChatCompletionChunkStream:
        cur_ctx = get_wandb_api_context()
        if not cur_ctx:
            # I don't think this should happen.
            raise ValueError("No context found")
        api_key = cur_ctx.api_key
        if not api_key:
            # I don't think this should happen.
            raise ValueError("No API key found")

        messages = kwargs["messages"]
        model = kwargs["model"]
        frequency_penalty = kwargs.get("frequency_penalty", NOT_GIVEN)
        max_tokens = kwargs.get("max_tokens", NOT_GIVEN)
        n = kwargs.get("n", NOT_GIVEN)
        presence_penalty = kwargs.get("presence_penalty", NOT_GIVEN)
        stream = kwargs.get("stream", False)
        stream_options = kwargs.get("stream_options", NOT_GIVEN)
        temperature = kwargs.get("temperature", NOT_GIVEN)
        top_p = kwargs.get("top_p", NOT_GIVEN)
        endpoint = kwargs.get("endpoint", "inference")

        headers = {
            "Content-Type": "application/json",
        }
        project_id = f"{self._client.entity}/{self._client.project}"
        data: dict[str, Any] = {
            "messages": messages,
        }

        if frequency_penalty is not NOT_GIVEN:
            data["frequency_penalty"] = frequency_penalty
        if max_tokens is not NOT_GIVEN:
            data["max_tokens"] = max_tokens
        if n is not NOT_GIVEN:
            data["n"] = n
        if presence_penalty is not NOT_GIVEN:
            data["presence_penalty"] = presence_penalty
        if stream is True:
            data["stream"] = stream
        if stream_options is not NOT_GIVEN:
            data["stream_options"] = stream_options
        if temperature is not NOT_GIVEN:
            data["temperature"] = temperature
        if top_p is not NOT_GIVEN:
            data["top_p"] = top_p

        auth = None
        if endpoint == "playground":
            auth = ("api", api_key)
            api = "create_stream" if stream else "create"
            url = f"{weave_trace_server_url()}/completions/{api}"
            data["model"] = model
            # Playground API wraps args
            data = {
                "inputs": data,
                "project_id": project_id,
                "track_llm_call": False,
            }
        elif endpoint == "inference":
            url = f"https://{INFERENCE_HOST}/v1/chat/completions"
            headers["Authorization"] = f"Bearer {api_key}"
            headers["OpenAI-Project"] = project_id
            # The inference service itself doesn't allow this prefix but
            # this client does to make it possible to switch between using the
            # playground APIs vs. the inference service directly.
            data["model"] = model.removeprefix("coreweave/")
        else:
            raise ValueError(f"Invalid endpoint: {endpoint}")

        request_stream = stream is True

        response = requests.post(
            url,
            auth=auth,
            headers=headers,
            json=data,
            stream=request_stream,
        )

        if response.status_code == 401:
            raise requests.HTTPError(
                f"{response.reason} - please make sure inference is enabled for entity {self._client.entity}",
                response=response,
            )

        response.raise_for_status()  # Raise exception on HTTP error

        if request_stream:
            return ChatCompletionChunkStream(response)

        # Non-streaming case
        d = response.json()
        if endpoint == "playground":
            d = d["response"]
        try:
            return ChatCompletion.model_validate(d)
        except ValidationError as e:
            print(d)
            raise e

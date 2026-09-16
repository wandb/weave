# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from typing_extensions import Required, TypedDict

__all__ = ["CompletionCreateParams", "Inputs"]


class CompletionCreateParams(TypedDict, total=False):
    inputs: Required[Inputs]

    project_id: Required[str]

    conversation_id: Optional[str]
    """Conversation ID to group related completions into a multi-turn conversation"""

    conversation_name: Optional[str]
    """Human-readable conversation name"""

    parent_id: Optional[str]
    """Parent call ID to nest this LLM call under"""

    source: Optional[str]
    """Source of the completion request (e.g. 'playground', 'signals')"""

    trace_id: Optional[str]
    """Trace ID to use for the LLM call (for nesting under a parent)"""

    track_llm_call: Optional[bool]
    """Whether to track this LLM call in the trace server"""

    wb_user_id: Optional[str]
    """Do not set directly. Server will automatically populate this field."""


class Inputs(TypedDict, total=False):
    model: Required[str]

    api_version: Optional[str]

    extra_headers: Optional[Dict[str, object]]

    frequency_penalty: Optional[float]

    function_call: Optional[str]

    functions: Optional[Iterable[object]]

    logit_bias: Optional[Dict[str, object]]

    logprobs: Optional[bool]

    max_completion_tokens: Optional[int]

    max_tokens: Optional[int]

    messages: Iterable[object]

    modalities: Optional[Iterable[object]]

    n: Optional[int]

    parallel_tool_calls: Optional[bool]

    presence_penalty: Optional[float]

    prompt: Optional[str]
    """
    Reference to a Weave Prompt object (e.g.,
    'weave:///entity/project/object/prompt_name:version'). If provided, the messages
    from this prompt will be prepended to the messages in this request. Template
    variables in the prompt messages can be substituted using the template_vars
    parameter.
    """

    reasoning_effort: Optional[str]

    response_format: Union[Dict[str, object], object, None]

    seed: Optional[int]

    stop: Union[str, Iterable[object], None]

    stream: Optional[bool]

    temperature: Optional[float]

    template_vars: Optional[Dict[str, object]]
    """Dictionary of template variables to substitute in prompt messages.

    Variables in messages like '{variable_name}' will be replaced with the
    corresponding values. Applied to both prompt messages (if prompt is provided)
    and regular messages.
    """

    timeout: Union[float, str, None]

    tool_choice: Union[str, Dict[str, object], None]

    tools: Optional[Iterable[object]]

    top_logprobs: Optional[int]

    top_p: Optional[float]

    user: Optional[str]

    vertex_credentials: Optional[str]
    """JSON string of Vertex AI service account credentials.

    When provided for vertex_ai models (e.g. vertex_ai/gemini-2.5-pro), used for
    authentication instead of api_key. Not persisted in trace storage.
    """

# This file contains the low-level dictionary definitions for the
# data types which can be logged to StreamTables and consumed
# by various Prompts products in the Weave UI. It is rare that an
# end user would directly interact with these types. Instead, they
# are more likely to be used by someone building an integration or
# an MLOps engineer setting up a pipeline for their team.

import typing
import datetime
import dataclasses


# TraceSpanDict is the lowest common denominator for a span
# in the Weave system. It conforms to the OpenTelemetry spec
class TraceSpanDict(typing.TypedDict):
    # **OpenTelemetry spec**

    # The ID of the span - typically a UUID
    span_id: str

    # The name of the span - typically the name of the operation
    name: str

    # The ID of the trace this span belongs to - typically a UUID
    trace_id: str

    # The status code conforming to the OpenTelemetry spec
    # I would like to use a literal `typing.Literal["SUCCESS", "ERROR", "UNSET"]`
    # here, but then you have to type it this way everywhere and probably causes
    # more problems than it solves.
    status_code: str

    # Start and end times in seconds since the epoch
    start_time_s: float
    end_time_s: float

    # The parent span ID - typically a UUID (optional)
    # if not set, this is a root span
    parent_id: typing.Optional[str]

    # **Weave specific keys**

    # Attributes are any key value pairs associated with the span,
    # typically known before the execution operation
    attributes: typing.Optional[typing.Dict[str, typing.Any]]

    # Inputs are the parameters to the operation
    inputs: typing.Optional[typing.Dict[str, typing.Any]]

    # Output is the result of the operation
    output: typing.Optional[typing.Any]

    # Summary is a dictionary of key value pairs that summarize
    # the execution of the operation. This data is typically only
    # available after the operation has completed, as a function
    # of the output.
    summary: typing.Optional[typing.Dict[str, typing.Any]]

    # Exception is any free form string describing an exception
    # that occurred during the execution of the operation
    exception: typing.Optional[str]


# LLM Completion is a specific type of span that is used to
# represent the execution of a language model. We use a structure
# modelled after OpenAI's API to represent the inputs and outputs.


class _LLMCompletionMessage(typing.TypedDict):
    role: typing.Optional[str]
    content: typing.Optional[str]


class _LLMCompletionInputs(typing.TypedDict):
    messages: typing.Optional[typing.List[_LLMCompletionMessage]]


class _LLMCompletionChoice(typing.TypedDict):
    message: typing.Optional[_LLMCompletionMessage]
    finish_reason: typing.Optional[str]
    index: typing.Optional[int]


class _LLMCompletionOutput(typing.TypedDict):
    id: typing.Optional[str]
    object: typing.Optional[str]
    model: typing.Optional[str]
    choices: typing.Optional[typing.List[_LLMCompletionChoice]]


class _LLMCompletionSummary(typing.TypedDict):
    prompt_tokens: typing.Optional[int]
    completion_tokens: typing.Optional[int]
    total_tokens: typing.Optional[int]


# Ideally we would inherit from TraceSpanDict here, but
# mypy doesn't support that level of sophistication yet.
# The only difference between this and TraceSpanDict is
# the further specification of the inputs, output, and summary.
class LLMCompletionDict(typing.TypedDict):
    # **OpenTelemetry spec**

    # The ID of the span - typically a UUID
    span_id: str

    # The name of the span - typically the name of the operation
    name: str

    # The ID of the trace this span belongs to - typically a UUID
    trace_id: str

    # The status code conforming to the OpenTelemetry spec
    # I would like to use a literal `typing.Literal["SUCCESS", "ERROR", "UNSET"]`
    # here, but then you have to type it this way everywhere and probably causes
    # more problems than it solves.
    status_code: str

    # Start and end times in seconds since the epoch
    start_time_s: float
    end_time_s: float

    # The parent span ID - typically a UUID (optional)
    # if not set, this is a root span
    parent_id: typing.Optional[str]

    # **Weave specific keys**

    # Attributes are any key value pairs associated with the span,
    # typically known before the execution operation
    attributes: typing.Optional[typing.Dict[str, typing.Any]]

    # Inputs are the parameters to the operation
    inputs: typing.Optional[_LLMCompletionInputs]

    # Output is the result of the operation
    output: typing.Optional[_LLMCompletionOutput]

    # Summary is a dictionary of key value pairs that summarize
    # the execution of the operation. This data is typically only
    # available after the operation has completed, as a function
    # of the output.
    summary: typing.Optional[_LLMCompletionSummary]

    # Exception is any free form string describing an exception
    # that occurred during the execution of the operation
    exception: typing.Optional[str]

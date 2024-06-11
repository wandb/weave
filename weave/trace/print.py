import weave
from rich import print

from weave.trace.refs import parse_uri, OpRef, ObjectRef
import json
import textwrap

# Bah... links aren't supported in Terminal.App
#   so we need to do some detection, which we can do on init...


def print_thing(call):
    def custom_format(v):
        if isinstance(v, OpRef):
            return f"<🔧 [link={v.ui_url}][underline]{v.name}:{v.digest[:4]}[/underline][/link]>"
        elif isinstance(v, ObjectRef):
            return f"<📦 [link={v.ui_url}][underline]{v.name}:{v.digest[:4]}[/underline][/link]>"
        elif isinstance(v, dict):
            return (
                "{"
                + ", ".join(
                    f"{key}: {custom_format(value)}" for key, value in v.items()
                )
                + "}"
            )
        elif isinstance(v, list):
            return "[" + ", ".join(custom_format(item) for item in v) + "]"
        else:
            return repr(v)

    call_emoji = "🍩"
    if call.exception:
        call_emoji = "❌"
    ref = parse_uri(call.op_name)
    op_name = ref.name
    # call_s = f'Call - {call_emoji} [link={call.ui_url}][underline black]{op_name} {call.id}[/underline black][/link]\n'
    call_s = f"Call - {call_emoji} [link={call.ui_url}]{op_name} {call.id}[/link]\n"
    call_s += f"  url: {call.ui_url}\n"
    inputs_s = custom_format(call.inputs)
    # if len(inputs_s) > 60:
    #     inputs_s = inputs_s[:60] + '...'
    call_s += f"  inputs: {inputs_s}\n"
    if call.output:
        output_s = custom_format(call.output)
        if len(output_s) > 60:
            output_s = output_s[:60] + "..."
        call_s += f"  output: {output_s}\n"
    if call.exception:
        exception_s = call.exception
        if len(exception_s) > 60:
            exception_s = exception_s[:60] + "..."
        call_s += f"  exception: '{exception_s}'\n"
    if call.attributes:
        attributes_s = custom_format(call.attributes)
        if len(attributes_s) > 60:
            attributes_s = attributes_s[:60] + "..."
        call_s += f"  attributes: {attributes_s}\n"
    if call.summary:
        summary_s = custom_format(call.summary)
        if len(summary_s) > 60:
            summary_s = summary_s[:60] + "..."
        call_s += f"  summary: {summary_s}\n"
    # Expensive, we'd need to do this in rollup or materialized view
    # call_s += f'  children: {len(list(call.children()))}\n'
    return call_s


if __name__ == "__main__":
    client = weave.init("weave-hooman1")
    # for call in client.calls('Evaluation.evaluate', filter={'output.llm_judge_accuracy.avg_support.mean': {'$gt': 2.3}}):
    for call in client.calls("Evaluation.evaluate"):
        print(print_thing(call))

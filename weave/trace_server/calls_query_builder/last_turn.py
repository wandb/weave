"""Query-time text projection of a call's last chat interaction.

The field is opt-in through columns, and uses the same SQL for selection,
filtering and ordering. Text blocks are joined with newlines; tool interactions
include function names, arguments and results. Media and reasoning are omitted.
Empty, unsupported and non-chat inputs produce NULL. References are not expanded.
"""

from weave.trace_server.opentelemetry.constants import INPUT_KEYS

LAST_TURN_FIELD = "summary.weave.last_turn_text"


def _bind(name: str, value: str, body: str) -> str:
    # Lambda arguments keep intermediate arrays local without query-global aliases.
    return f"arrayMap({name} -> {body}, [{value}])[1]"


def _join(values: str) -> str:
    return f"arrayStringConcat(arrayFilter(s -> s != '', {values}), '\\n')"


def _value_text(value: str) -> str:
    return (
        f"multiIf(JSONType({value}) = 'String', JSONExtractString({value}), "
        f"{value} IN ('', 'null'), '', {value})"
    )


def _content_text(content: str) -> str:
    return _bind(
        "content",
        content,
        "if(JSONType(content) = 'String', JSONExtractString(content), "
        + _join(
            "arrayMap(part -> multiIf("
            "JSONType(part) = 'String', JSONExtractString(part), "
            "JSONHas(part, 'text') AND NOT JSONHas(part, 'thinking') AND "
            "JSONExtractString(part, 'type') IN ('', 'text', 'input_text', 'output_text'), "
            "JSONExtractString(part, 'text'), "
            "JSONExtractString(part, 'type') = 'text', "
            "JSONExtractString(part, 'content'), ''), JSONExtractArrayRaw(content))"
        )
        + ")",
    )


def _tool(tool_id: str, name: str, arguments: str, result: str = "''") -> str:
    return f"tuple({tool_id}, {_join(f'[{name}, {arguments}, {result}]')})"


def _message(role: str, text: str, tool_id: str = "''", tools: str = "[]") -> str:
    """Normalize to (role, text, tool result ID, [(invocation ID, invocation text)])."""
    return f"tuple({role}, {text}, {tool_id}, {tools})"


def _plain_message(content: str, role: str = "'user'") -> str:
    return _message(role, _content_text(content))


def _plain_field(obj: str, key: str) -> str:
    return _plain_message(f"JSONExtractRaw({obj}, '{key}')")


def _standard_message() -> str:
    tools = (
        "arrayConcat("
        + ", ".join(
            [
                "arrayMap(tc -> "
                + _tool(
                    "JSONExtractString(tc, 'id')",
                    "JSONExtractString(tc, 'function', 'name')",
                    _value_text("JSONExtractRaw(tc, 'function', 'arguments')"),
                )
                + ", JSONExtractArrayRaw(m, 'tool_calls'))",
                "arrayMap(tc -> "
                + _tool(
                    "JSONExtractString(tc, 'id')",
                    "JSONExtractString(tc, 'name')",
                    _value_text("JSONExtractRaw(tc, 'input')"),
                )
                + ", arrayFilter(tc -> JSONExtractString(tc, 'type') = 'tool_use', "
                "JSONExtractArrayRaw(m, 'content')))",
            ]
        )
        + ")"
    )
    normal = _message(
        "JSONExtractString(m, 'role')",
        _content_text("JSONExtractRaw(m, 'content')"),
        "JSONExtractString(m, 'tool_call_id')",
        tools,
    )
    tool_result = _message(
        "'tool'",
        _content_text("JSONExtractRaw(result, 'content')"),
        "JSONExtractString(result, 'tool_use_id')",
    )
    return _bind(
        "result",
        "arrayFirst(p -> JSONExtractString(p, 'type') = 'tool_result', "
        "JSONExtractArrayRaw(m, 'content'))",
        f"if(result != '', {tool_result}, {normal})",
    )


def _agent_messages(source: str) -> str:
    assistant = _message(
        "'assistant'",
        _content_text("JSONExtractRaw(m, 'content')"),
        tools="arrayMap(tc -> "
        + _tool(
            "JSONExtractString(tc, 'id')",
            "JSONExtractString(tc, 'name')",
            _value_text("JSONExtractRaw(tc, 'input')"),
        )
        + ", arrayFilter(tc -> JSONHas(tc, 'name') AND JSONHas(tc, 'id'), "
        "JSONExtractArrayRaw(m, 'content')))",
    )
    user_part = (
        "if(JSONHas(p, 'tool_use_id'), "
        + _message(
            "'tool'",
            _content_text("JSONExtractRaw(p, 'content')"),
            "JSONExtractString(p, 'tool_use_id')",
        )
        + ", "
        + _plain_message("JSONExtractRaw(p, 'text')")
        + ")"
    )
    return (
        "arrayFlatten(arrayMap(m -> multiIf("
        "JSONExtractString(m, 'role') = 'result' OR "
        "(JSONExtractString(m, 'role') = 'system' AND "
        "JSONExtractString(m, 'subtype') = 'init'), [], "
        f"JSONExtractString(m, 'role') = 'assistant', [{assistant}], "
        "JSONExtractString(m, 'role') = 'user' AND JSONType(m, 'content') = 'Array', "
        f"arrayMap(p -> {user_part}, arrayFilter(p -> JSONHas(p, 'tool_use_id') OR "
        "JSONHas(p, 'text'), JSONExtractArrayRaw(m, 'content'))), "
        f"[{_standard_message()}]), {source}))"
    )


def _responses_messages(source: str) -> str:
    tools = _tool(
        "JSONExtractString(m, 'call_id')",
        "JSONExtractString(m, 'name')",
        _value_text("JSONExtractRaw(m, 'arguments')"),
        _value_text(
            "if(JSONExtractString(m, 'type') = 'mcp_call', JSONExtractRaw(m, 'output'), "
            "JSONExtractRaw(arrayFirst(r -> JSONExtractString(r, 'type') = 'function_call_output' "
            "AND JSONExtractString(r, 'call_id') = JSONExtractString(m, 'call_id'), "
            "JSONExtractArrayRaw(response_input)), 'output'))"
        ),
    )
    message = (
        "if(JSONExtractString(m, 'type') IN ('function_call', 'mcp_call'), "
        + _message("'assistant'", "''", tools=f"[{tools}]")
        + f", {_standard_message()})"
    )
    return _bind(
        "response_input",
        source,
        "if(JSONType(response_input) = 'String', "
        f"[{_plain_message('response_input')}], "
        f"arrayMap(m -> {message}, arrayFilter(m -> "
        "JSONExtractString(m, 'type') NOT IN ('reasoning', 'function_call_output', 'mcp_list_tools'), "
        "JSONExtractArrayRaw(response_input))))",
    )


def _google_message() -> str:
    part_text = "multiIf(JSONHas(p, 'text'), JSONExtractString(p, 'text'), "
    part_text += (
        "JSONHas(p, 'functionResponse'), "
        + _join(
            "[JSONExtractString(p, 'functionResponse', 'name'), "
            + _value_text("JSONExtractRaw(p, 'functionResponse', 'response')")
            + "]"
        )
        + ", '')"
    )
    tools = (
        "arrayMap(p -> "
        + _tool(
            "JSONExtractString(p, 'functionCall', 'id')",
            "JSONExtractString(p, 'functionCall', 'name')",
            _value_text("JSONExtractRaw(p, 'functionCall', 'args')"),
        )
        + ", arrayFilter(p -> JSONHas(p, 'functionCall'), JSONExtractArrayRaw(m, 'parts')))"
    )
    return _message(
        "if(JSONExtractString(m, 'role') = 'model', 'assistant', JSONExtractString(m, 'role'))",
        _join(f"arrayMap(p -> {part_text}, JSONExtractArrayRaw(m, 'parts'))"),
        tools=tools,
    )


def _langchain_message() -> str:
    return _message(
        "if(JSONExtractString(m, 'kwargs', 'tool_call_id') != '', 'tool', "
        "transform(JSONExtractString(m, 'id', -1), "
        "['SystemMessage', 'HumanMessage', 'AIMessage', 'ToolMessage'], "
        "['system', 'user', 'assistant', 'tool'], 'assistant'))",
        _content_text("JSONExtractRaw(m, 'kwargs', 'content')"),
        "JSONExtractString(m, 'kwargs', 'tool_call_id')",
        "arrayMap(tc -> "
        + _tool(
            "JSONExtractString(tc, 'id')",
            "JSONExtractString(tc, 'name')",
            _value_text("JSONExtractRaw(tc, 'args')"),
        )
        + ", JSONExtractArrayRaw(m, 'kwargs', 'tool_calls'))",
    )


def _otel_message() -> str:
    normal = _message(
        "if(JSONExtractString(m, 'role') = '', 'user', JSONExtractString(m, 'role'))",
        _content_text("JSONExtractRaw(m, 'parts')"),
        tools="arrayMap(p -> "
        + _tool(
            "JSONExtractString(p, 'id')",
            "JSONExtractString(p, 'name')",
            _value_text("JSONExtractRaw(p, 'arguments')"),
        )
        + ", arrayFilter(p -> JSONExtractString(p, 'type') = 'tool_call', "
        "JSONExtractArrayRaw(m, 'parts')))",
    )
    result = _message(
        "'tool'",
        _value_text(
            "if(JSONHas(r, 'result'), JSONExtractRaw(r, 'result'), JSONExtractRaw(r, 'response'))"
        ),
        "JSONExtractString(r, 'id')",
    )
    return _bind(
        "r",
        "arrayFirst(p -> JSONExtractString(p, 'type') = 'tool_call_response', "
        "JSONExtractArrayRaw(m, 'parts'))",
        f"multiIf(JSONType(m) = 'String', {_plain_message('m')}, "
        f"r != '', {result}, JSONHas(m, 'parts'), {normal}, {_standard_message()})",
    )


def _adk_messages() -> str:
    tool = _tool(
        "JSONExtractString(p, 'function_call', 'id')",
        "JSONExtractString(p, 'function_call', 'name')",
        _value_text("JSONExtractRaw(p, 'function_call', 'args')"),
    )
    message = _message(
        "if(JSONExtractString(m, 'role') = 'model', 'assistant', 'user')",
        _content_text("JSONExtractRaw(m, 'parts')"),
        tools=f"arrayMap(p -> {tool}, arrayFilter(p -> JSONHas(p, 'function_call'), JSONExtractArrayRaw(m, 'parts')))",
    )
    results = (
        "arrayMap(p -> "
        + _plain_field("p", "message")
        + ", arrayFilter(p -> JSONType(p, 'message') = 'String', "
        "arrayMap(p -> JSONExtractRaw(p, 'function_response', 'response'), JSONExtractArrayRaw(m, 'parts'))))"
    )
    return (
        "arrayConcat(["
        + _plain_message(
            "JSONExtractRaw(prompt, 'config', 'system_instruction')", "'system'"
        )
        + "], arrayFlatten(arrayMap(m -> arrayConcat("
        + results
        + ", "
        + _bind("msg", message, "if(msg.2 != '' OR notEmpty(msg.4), [msg], [])")
        + "), JSONExtractArrayRaw(prompt, 'contents'))))"
    )


def _normalized_messages() -> str:
    responses_input = _responses_messages("JSONExtractRaw(i, 'input')")
    responses_messages = _responses_messages("JSONExtractRaw(i, 'messages')")
    otel_key = (
        "arrayFirst(k -> JSONHas(i, k), ["
        + ", ".join(f"'{key}'" for key in INPUT_KEYS)
        + "])"
    )
    otel = _bind(
        "prompt",
        f"JSONExtractRaw(i, {otel_key})",
        f"multiIf(JSONHas(i, 'gcp.vertex.agent.llm_request'), {_adk_messages()}, "
        "JSONType(prompt) = 'String', "
        f"[{_plain_message('prompt')}], JSONHas(prompt, 'messages'), "
        f"arrayMap(m -> {_otel_message()}, JSONExtractArrayRaw(prompt, 'messages')), "
        "JSONType(prompt) = 'Array', "
        f"arrayMap(m -> {_otel_message()}, JSONExtractArrayRaw(prompt)), "
        f"JSONHas(prompt, 'role'), arrayMap(m -> {_otel_message()}, [prompt]), "
        f"JSONHas(prompt, 'prompt'), [{_plain_field('prompt', 'prompt')}], [])",
    )
    source = (
        "multiIf("
        "arrayExists(m -> JSONExtractString(m, 'role') = 'result' OR "
        "(JSONExtractString(m, 'role') = 'system' AND JSONExtractString(m, 'subtype') = 'init'), "
        "JSONExtractArrayRaw(o, 'messages')), "
        + _agent_messages("JSONExtractArrayRaw(o, 'messages')")
        + ", JSONExtractString(i, 'history', 1, 'subtype') = 'init', "
        + _agent_messages("JSONExtractArrayRaw(i, 'history')")
        + f", (JSONHas(a, 'otel_span') OR otel != '') AND {otel_key} != '', {otel}, "
        "JSONType(i, 'messages', 1) = 'Array', "
        f"arrayMap(m -> {_langchain_message()}, JSONExtractArrayRaw(i, 'messages', 1)), "
        "arrayExists(m -> JSONExtractString(m, 'type') IN "
        "('message', 'function_call', 'function_call_output', 'mcp_call', 'mcp_list_tools', 'reasoning'), "
        f"JSONExtractArrayRaw(i, 'messages')), {responses_messages}, "
        "JSONType(i, 'messages') = 'Array', "
        f"arrayMap(m -> {_standard_message()}, JSONExtractArrayRaw(i, 'messages')), "
        "JSONType(i, 'contents') = 'Array', "
        f"arrayMap(m -> {_google_message()}, JSONExtractArrayRaw(i, 'contents')), "
        "JSONType(i, 'contents') = 'String', "
        f"[{_plain_field('i', 'contents')}], "
        "JSONType(i, 'input') IN ('String', 'Array'), "
        f"{responses_input}, "
        "JSONType(i, 'message') = 'String' AND startsWith(JSONExtractString(i, 'self', '__class__', 'module'), 'google.genai'), "
        f"[{_plain_field('i', 'message')}], "
        "JSONType(i, 'prompt') = 'String' AND (JSONHas(o, 'data') OR "
        "startsWith(JSONExtractString(i, 'model'), 'gpt-image') OR "
        "startsWith(JSONExtractString(i, 'model'), 'dall-e')), "
        f"[{_plain_field('i', 'prompt')}], [])"
    )
    fallback = (
        "multiIf("
        f"(JSONHas(a, 'otel_span') OR otel != '') AND {otel_key} != '', ["
        + _plain_message(
            "if(JSONHas(a, 'system'), JSONExtractRaw(a, 'system'), "
            "JSONExtractRaw(a, 'model_parameters', 'system'))"
        )
        + "], JSONType(i, 'messages') = 'Array', "
        f"[{_plain_field('i', 'system')}], "
        "JSONType(i, 'input') IN ('Array', 'String'), "
        f"[{_plain_field('i', 'instructions')}], "
        "JSONHas(i, 'contents'), "
        "[" + _plain_field("JSONExtractRaw(i, 'config')", "systemInstruction") + "], "
        "JSONExtractString(i, 'history', 1, 'subtype') = 'init', "
        f"[{_plain_field('i', 'prompt')}], [])"
    )
    return _bind(
        "normalized",
        f"arrayFilter(m -> m.1 != '', {source})",
        f"if(empty(normalized), {fallback}, normalized)",
    )


def last_turn_text_sql(inputs: str, output: str, attributes: str, otel: str) -> str:
    """Return a Nullable(String) expression over the assembled logical call."""
    tool_text = _join("arrayMap(tc -> tc.2, m.4)")
    trailing = "arraySlice(messages, arrayLastIndex(m -> m.1 != 'tool', messages) + 1)"
    invoking_indices = (
        "arraySort(arrayDistinct(arrayFilter(idx -> idx > 0, "
        "arrayMap(result -> if(result.3 = '', 0, arrayLastIndex(m -> "
        "arrayExists(tc -> tc.1 = result.3, m.4), messages)), trailing))))"
    )
    tool_group = _bind(
        "trailing",
        trailing,
        _join(
            "arrayConcat("
            f"arrayMap(m -> {tool_text}, arrayMap(idx -> messages[idx], {invoking_indices})), "
            "arrayMap(m -> m.2, trailing))"
        ),
    )
    single = _bind("m", "messages[-1]", _join(f"[m.2, {tool_text}]"))
    body = _bind(
        "messages",
        _normalized_messages(),
        f"nullIf(if(messages[-1].1 = 'tool', {tool_group}, {single}), '')",
    )
    return (
        f"arrayMap((i, o, a, otel) -> {body}, [ifNull({inputs}, '{{}}')], "
        f"[ifNull({output}, '{{}}')], [ifNull({attributes}, '{{}}')], "
        f"[ifNull({otel}, '')])[1]"
    )

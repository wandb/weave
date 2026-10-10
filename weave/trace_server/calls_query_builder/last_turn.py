"""Query-time text projection of a call's last chat interaction.

The field is opt-in through columns, and uses the same SQL for selection,
filtering and ordering. Provider normalization preserves text-block boundaries;
message/tool components are joined with newlines. Tool interactions include
function names, arguments and results. Media and reasoning are omitted.
Empty, unsupported and non-chat inputs produce NULL. References are not expanded.
"""

import re

from weave.trace_server.opentelemetry.constants import INPUT_KEYS, OUTPUT_KEYS

LAST_TURN_FIELD = "summary.weave.last_turn_text"
LAST_TURN_MAX_BLOCK_SIZE = 256
LAST_TURN_COST_PAGE_MAX_ROWS = 1000
LAST_TURN_COLUMN = "__weave_last_turn_text"
LAST_TURN_INPUT_COLUMNS = ("__lt_inputs", "__lt_output", "__lt_attributes", "__lt_otel")


def _bind(name: str, value: str, body: str) -> str:
    # Lambda arguments keep intermediate arrays local without query-global aliases.
    return f"arrayMap({name} -> {body}, [{value}])[1]"


def _join(values: str, separator: str = "\\n") -> str:
    return f"arrayStringConcat(arrayFilter(s -> s != '', {values}), '{separator}')"


def _truthy(value: str) -> str:
    return f"({value} NOT IN ('', 'null', 'false', '0', '\"\"'))"


def _tokens(value: str) -> str:
    return f'extractAll({value}, \'"(?:[^"\\\\\\\\]|\\\\\\\\.)*"|[^\\\\s"{{}}\\\\[\\\\],:]+|[{{}}\\\\[\\\\],:]\')'


def _json_stringify_body(value: str, pretty: bool = False) -> str:
    tokens = _tokens(value)
    if not pretty:
        quoted = (
            "arrayStringConcat(arrayMap(escape -> multiIf(escape = '\\\\u2028', ' ', escape = '\\\\u2029', ' ', escape = '\\\\/', '/', escape), "
            "extractAll(toJSONString(JSONExtractString(token)), '\\\\\\\\u[0-9a-fA-F]{4}|\\\\\\\\.|[^\\\\\\\\]+')))"
        )
        scalar = (
            f"multiIf(startsWith(token, '\"'), {quoted}, token IN ('true', 'false', 'null'), token, "
            "replaceRegexpOne(toString(toFloat64OrZero(token)), 'e([0-9])', 'e+\\\\1'))"
        )
        obj = (
            "arrayStringConcat(arrayMap(pos -> concat(frame.2[pos * 2 + 1], ':', frame.2[pos * 2 + 2]), "
            "arraySort(pos -> "
            + _bind(
                "key",
                "JSONExtractString(frame.2[pos * 2 + 1])",
                "tuple(NOT (match(key, '^(0|[1-9][0-9]*)$') AND length(key) <= 10 AND toUInt64OrZero(key) < 4294967295), if(match(key, '^(0|[1-9][0-9]*)$') AND length(key) <= 10 AND toUInt64OrZero(key) < 4294967295, toUInt64OrZero(key), pos))",
            )
            + ", range(toUInt64(length(frame.2) / 2)))), ',')"
        )
        completed = _bind(
            "frame",
            "stack[-1]",
            "if(frame.1 = '[', concat('[', arrayStringConcat(frame.2, ','), ']'), concat('{', "
            + obj
            + ", '}'))",
        )
        fold = (
            "arrayFold((stack, token) -> multiIf(token IN ('{', '['), arrayPushBack(stack, tuple(token, CAST([], 'Array(String)'))), "
            "token IN (',', ':'), stack, token IN ('}', ']'), "
            "arrayPushBack(arrayPopBack(arrayPopBack(stack)), tuple(stack[-2].1, arrayPushBack(stack[-2].2, "
            + completed
            + "))), "
            "arrayPushBack(arrayPopBack(stack), tuple(stack[-1].1, arrayPushBack(stack[-1].2, "
            + scalar
            + ")))), "
            + tokens
            + ", [tuple('', CAST([], 'Array(String)'))])[-1].2[1]"
        )
        return fold
    tokens = _tokens(f"__weave_last_turn_json({value})")
    return _bind(
        "tokens",
        tokens,
        _bind(
            "depths",
            "arrayCumSum(arrayMap(t -> multiIf(t IN ('{', '['), 1, t IN ('}', ']'), -1, 0), tokens))",
            "arrayStringConcat(arrayMap((t, pos) -> multiIf("
            "t IN ('{', '['), concat(t, if(tokens[pos + 1] IN ('}', ']'), '', concat('\\n', repeat('  ', toUInt64(greatest(depths[pos], 0)))))), "
            "t IN ('}', ']'), concat(if(tokens[pos - 1] IN ('{', '['), '', concat('\\n', repeat('  ', toUInt64(greatest(depths[pos], 0))))), t), "
            "t = ',', concat(',\\n', repeat('  ', toUInt64(greatest(depths[pos], 0)))), "
            "t = ':', ': ', t), tokens, arrayEnumerate(tokens)))",
        ),
    )


def _json_stringify(value: str, pretty: bool = False) -> str:
    # Serialize deferred JSON tokens only after selecting the last message or tool group.
    kind = "P" if pretty else "J"
    return _bind(
        "json",
        value,
        f"if(json = '', '', concat(char(0), '{kind}', base64Encode(json), char(0)))",
    )


def with_last_turn_sql_helpers(sql: str) -> str:
    safe_json = (
        "if(match(raw, '[0-9]{20}'), arrayStringConcat(arrayMap(token -> "
        "if(match(token, '^-?[0-9]{20,}$'), "
        "replaceRegexpOne(toString(toFloat64OrZero(token)), '^([^e]+)$', '\\\\1e0'), token), "
        + _tokens("raw")
        + ")), raw)"
    )
    definitions = ",\n".join(
        [
            f"raw -> {safe_json} AS __weave_last_turn_safe_json",
            f"raw -> {_json_stringify_body('raw')} AS __weave_last_turn_json",
            f"raw -> {_json_stringify_body('raw', pretty=True)} AS __weave_last_turn_pretty_json",
        ]
    )
    stripped = sql.lstrip()
    rest = ", " + stripped[4:].lstrip() if stripped.startswith("WITH") else "\n" + sql
    return "WITH " + definitions + rest


def _prepare_json_reads(sql: str) -> str:
    # Escape literal NULs before mixing text with deferred JSON tokens.
    pattern = re.compile(r"\bJSONExtract(?:ArrayRaw|String)\(")
    result = []
    cursor = 0
    while match := pattern.search(sql, cursor):
        result.append(sql[cursor : match.start()])
        depth = 1
        pos = match.end()
        quoted = False
        while depth:
            char = sql[pos]
            if char == "\\" and quoted:
                pos += 2
                continue
            if char == "'":
                quoted = not quoted
            elif not quoted:
                depth += (char == "(") - (char == ")")
            pos += 1
        call = match.group() + _prepare_json_reads(sql[match.end() : pos - 1]) + ")"
        if match.group().startswith("JSONExtractString"):
            metadata = re.search(
                r",\s*'(?:role|type|id|tool_call_id|tool_use_id|call_id|subtype|model|module|qualname|status|model_name)'\)$",
                call,
            )
            result.append(
                call
                if metadata
                else f"replaceAll({call}, char(0), concat(char(0), char(0)))"
            )
        else:
            result.append(f"arrayMap(raw -> __weave_last_turn_safe_json(raw), {call})")
        cursor = pos
    result.append(sql[cursor:])
    return "".join(result)


def _value_text(value: str) -> str:
    return _bind(
        "value",
        value,
        "multiIf(JSONType(value) = 'String', JSONExtractString(value), "
        "value = '', '', " + _json_stringify("value") + ")",
    )


def _content_text(content: str) -> str:
    return _bind(
        "content",
        f"__weave_last_turn_safe_json({content})",
        "multiIf(JSONType(content) = 'String', JSONExtractString(content), "
        "arrayExists(part -> JSONType(part) NOT IN ('String', 'Object', 'Array'), JSONExtractArrayRaw(content)), NULL, "
        + _join(
            "arrayMap(part -> multiIf("
            "JSONType(part) = 'String', JSONExtractString(part), "
            "JSONExtractString(part, 'type') = 'text' AND JSONType(part, 'text') = 'String', "
            "JSONExtractString(part, 'text'), "
            "JSONType(part, 'content') = 'String', "
            "JSONExtractString(part, 'content'), ''), JSONExtractArrayRaw(content))",
            "",
        )
        + ")",
    )


def _text_blocks(
    content: str,
    separator: str = "",
    predicate: str = "JSONExtractString(p, 'type') = 'text'",
) -> str:
    return _bind(
        "blocks",
        f"__weave_last_turn_safe_json({content})",
        (
            "if(JSONType(blocks) = 'String', JSONExtractString(blocks), "
            f"arrayStringConcat(arrayMap(p -> JSONExtractString(p, 'text'), "
            f"arrayFilter(p -> {predicate}, JSONExtractArrayRaw(blocks))), '{separator}'))"
        ),
    )


def _raw_message() -> str:
    return _message(
        "JSONExtractString(m, 'role')",
        _content_text("JSONExtractRaw(m, 'content')"),
        "JSONExtractString(m, 'tool_call_id')",
        "arrayMap(tc -> "
        + _tool(
            "JSONExtractString(tc, 'id')",
            "JSONExtractString(tc, 'function', 'name')",
            "JSONExtractString(tc, 'function', 'arguments')",
        )
        + ", JSONExtractArrayRaw(m, 'tool_calls'))",
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
        "if(notEmpty(arrayFilter(tc -> JSONExtractString(tc, 'type') = 'tool_use', JSONExtractArrayRaw(m, 'content'))), "
        + ", ".join(
            [
                "arrayMap(tc -> "
                + _tool(
                    "JSONExtractString(tc, 'id')",
                    "JSONExtractString(tc, 'name')",
                    _json_stringify("JSONExtractRaw(tc, 'input')"),
                )
                + ", arrayFilter(tc -> JSONExtractString(tc, 'type') = 'tool_use', "
                "JSONExtractArrayRaw(m, 'content')))",
                "arrayMap(tc -> "
                + _tool(
                    "JSONExtractString(tc, 'id')",
                    "JSONExtractString(tc, 'function', 'name')",
                    "JSONExtractString(tc, 'function', 'arguments')",
                )
                + ", JSONExtractArrayRaw(m, 'tool_calls'))",
            ]
        )
        + ")"
    )
    normal = _message(
        "JSONExtractString(m, 'role')",
        _bind(
            "parts",
            "arrayFilter(p -> JSONExtractString(p, 'type') NOT IN ('tool_use', 'tool_result'), JSONExtractArrayRaw(m, 'content'))",
            "multiIf(arrayExists(p -> JSONType(p) NOT IN ('String', 'Object', 'Array'), parts), NULL, empty(parts), "
            + _content_text("JSONExtractRaw(m, 'content')")
            + ", arrayStringConcat(arrayMap(p -> if(JSONExtractString(p, 'type') = 'text', if(JSONType(p, 'text') = 'String', JSONExtractString(p, 'text'), ''), "
            + _content_text("concat('[', p, ']')")
            + "), parts)))",
        ),
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
        f"if(JSONHas(result, 'content') AND JSONHas(result, 'tool_use_id'), {tool_result}, {normal})",
    )


def _agent_messages(source: str) -> str:
    assistant = _message(
        "'assistant'",
        _text_blocks(
            "JSONExtractRaw(m, 'content')",
            "\\n",
            "JSONHas(p, 'text') AND NOT JSONHas(p, 'thinking')",
        ),
        tools="arrayMap(tc -> "
        + _tool(
            "JSONExtractString(tc, 'id')",
            "JSONExtractString(tc, 'name')",
            _json_stringify("JSONExtractRaw(tc, 'input')"),
        )
        + ", arrayFilter(tc -> JSONHas(tc, 'name') AND JSONHas(tc, 'id'), "
        "JSONExtractArrayRaw(m, 'content')))",
    )
    user_part = (
        "if(JSONHas(p, 'tool_use_id'), "
        + _message(
            "'tool'",
            _bind(
                "result_content",
                "__weave_last_turn_safe_json(JSONExtractRaw(p, 'content'))",
                "if(JSONType(result_content) = 'Array', "
                "if(arrayExists(p -> JSONExtractString(p, 'type') = 'text', JSONExtractArrayRaw(result_content)), "
                + _text_blocks("result_content", "\\n")
                + ", concat('```json\\n', "
                + _json_stringify("result_content", pretty=True)
                + ", '\\n```')), "
                + _value_text("result_content")
                + ")",
            ),
            "JSONExtractString(p, 'tool_use_id')",
        )
        + ", "
        + _plain_message("JSONExtractRaw(p, 'text')")
        + ")"
    )
    return (
        "if(arrayExists(m -> JSONType(m) = 'Null' OR (JSONExtractString(m, 'role') IN ('user', 'assistant') AND arrayExists(p -> JSONType(p) != 'Object', JSONExtractArrayRaw(m, 'content'))), "
        + source
        + "), [], arrayFlatten(arrayMap(m -> multiIf("
        "JSONExtractString(m, 'role') = 'result' OR "
        "(JSONExtractString(m, 'role') = 'system' AND "
        "JSONExtractString(m, 'subtype') = 'init'), [], "
        f"JSONExtractString(m, 'role') = 'assistant' AND JSONType(m, 'content') = 'Array', [{assistant}], "
        "JSONExtractString(m, 'role') = 'user' AND JSONType(m, 'content') = 'Array', "
        f"arrayMap(p -> {user_part}, arrayFilter(p -> JSONHas(p, 'tool_use_id') OR "
        "JSONHas(p, 'text'), JSONExtractArrayRaw(m, 'content'))), "
        f"JSONExtractString(m, 'role') = 'system' OR (JSONExtractString(m, 'role') = 'user' AND JSONType(m, 'content') = 'String'), [{_raw_message()}], []), {source})))"
    )


def _responses_messages(source: str) -> str:
    retained = _bind(
        "items",
        "JSONExtractArrayRaw(response_input)",
        "if(JSONExtractString(items[-1], 'role') != 'tool' AND "
        "arrayAll(m -> NOT JSONHas(m, 'type') AND JSONType(m, 'role') = 'String' "
        "AND JSONType(m, 'content') = 'String', items), arraySlice(items, -1), items)",
    )
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
        + ", "
        + _message(
            "JSONExtractString(m, 'role')",
            _text_blocks(
                "JSONExtractRaw(m, 'content')",
                predicate="JSONExtractString(p, 'type') IN ('text', 'input_text', 'output_text') AND JSONType(p, 'text') = 'String'",
            ),
        )
        + ")"
    )
    return _bind(
        "response_input",
        f"__weave_last_turn_safe_json({source})",
        "multiIf(arrayExists(m -> JSONType(m) NOT IN ('Object', 'Array') OR (JSONExtractString(m, 'type') = 'message' AND JSONExtractRaw(m, 'content') NOT IN ('', 'null') AND JSONType(m, 'content') != 'Array'), JSONExtractArrayRaw(response_input)), [], JSONType(response_input) = 'String', "
        f"[{_plain_message('response_input')}], "
        f"arrayMap(m -> {message}, arrayFilter(m -> "
        "JSONExtractString(m, 'type') IN ('message', 'function_call', 'mcp_call') OR "
        "(NOT JSONHas(m, 'type') AND JSONHas(m, 'role') AND JSONHas(m, 'content')), "
        + retained
        + ")))",
    )


def _response_message_valid() -> str:
    return (
        "JSONType(m) = 'Object' AND ("
        "(JSONType(m, 'role') = 'String' AND JSONType(m, 'content') = 'String') OR "
        "multiIf(JSONExtractString(m, 'type') = 'function_call', "
        "arrayAll(k -> JSONType(m, k) = 'String', ['id', 'name', 'arguments', 'call_id', 'status']), "
        "JSONExtractString(m, 'type') = 'function_call_output', JSONHas(m, 'output') AND JSONType(m, 'call_id') = 'String', "
        "JSONExtractString(m, 'type') = 'mcp_call', arrayAll(k -> JSONType(m, k) = 'String', ['id', 'name', 'arguments']), "
        "JSONExtractString(m, 'type') = 'mcp_list_tools', JSONType(m, 'tools') = 'Array', "
        "JSONExtractString(m, 'type') = 'message', JSONType(m, 'id') = 'String' AND JSONType(m, 'role') = 'String' AND "
        "JSONType(m, 'content') = 'Array' AND arrayAll(p -> JSONType(p) = 'Object' AND "
        "((JSONExtractString(p, 'type') IN ('text', 'input_text', 'output_text') AND JSONType(p, 'text') = 'String') OR "
        "(JSONExtractString(p, 'type') IN ('audio', 'input_audio', 'output_audio') AND JSONType(p, 'audio') = 'Object')), JSONExtractArrayRaw(m, 'content')), "
        "JSONExtractString(m, 'type') = 'reasoning'))"
    )


def _google_message() -> str:
    args = _json_stringify(
        "if(JSONExtractRaw(p, 'functionCall', 'args') IN ('', 'null'), '{}', JSONExtractRaw(p, 'functionCall', 'args'))"
    )
    part_text = (
        "multiIf(JSONExtractString(p, 'text') != '', '', JSONType(p, 'functionCall') = 'Object', "
        + args
        + ", "
    )
    part_text += (
        "JSONType(p, 'functionResponse') = 'Object', "
        + _value_text(
            "if(JSONExtractRaw(p, 'functionResponse', 'response') IN ('', 'null'), '{}', JSONExtractRaw(p, 'functionResponse', 'response'))"
        )
        + ", '')"
    )
    tools = (
        "arrayMap(p -> "
        + _tool(
            "JSONExtractString(p, 'functionCall', 'id')",
            "JSONExtractString(p, 'functionCall', 'name')",
            args,
        )
        + ", arrayFilter(p -> JSONHas(p, 'functionCall'), JSONExtractArrayRaw(m, 'parts')))"
    )
    return _message(
        "if(JSONExtractString(m, 'role') = 'model', 'assistant', JSONExtractString(m, 'role'))",
        "concat("
        + _join(
            "arrayMap(p -> JSONExtractString(p, 'text'), JSONExtractArrayRaw(m, 'parts'))"
        )
        + ", "
        + _join(f"arrayMap(p -> {part_text}, JSONExtractArrayRaw(m, 'parts'))", "")
        + ")",
        tools=tools,
    )


def _langchain_message() -> str:
    return _message(
        "if(JSONExtractString(m, 'kwargs', 'tool_call_id') != '', 'tool', "
        "transform(JSONExtractString(m, 'id', -1), "
        "['SystemMessage', 'HumanMessage', 'AIMessage', 'ToolMessage'], "
        "['system', 'user', 'assistant', 'tool'], if(JSONExtractString(m, 'kwargs', 'type') != '', JSONExtractString(m, 'kwargs', 'type'), 'assistant')))",
        _text_blocks("JSONExtractRaw(m, 'kwargs', 'content')"),
        "JSONExtractString(m, 'kwargs', 'tool_call_id')",
        "arrayMap(tc -> "
        + _tool(
            "JSONExtractString(tc, 'id')",
            "JSONExtractString(tc, 'name')",
            _json_stringify("JSONExtractRaw(tc, 'args')"),
        )
        + ", JSONExtractArrayRaw(m, 'kwargs', 'tool_calls'))",
    )


def _semconv_message() -> str:
    normal = _message(
        "if(JSONExtractString(m, 'role') = '', 'user', JSONExtractString(m, 'role'))",
        "arrayStringConcat(arrayMap(p -> "
        + "if(JSONExtractString(p, 'type') = 'text' AND JSONType(p, 'content') = 'Object', '[object Object]', "
        + _value_text("JSONExtractRaw(p, 'content')")
        + ")"
        + ", arrayFilter(p -> JSONExtractString(p, 'type') NOT IN ('tool_call', 'tool_call_response') AND "
        + _truthy("JSONExtractRaw(p, 'content')")
        + ", JSONExtractArrayRaw(m, 'parts'))), '\\n')",
        tools="arrayMap((p, idx) -> "
        + _tool(
            "if(JSONExtractString(p, 'id') = '', concat('tool_', toString(idx - 1)), JSONExtractString(p, 'id'))",
            "JSONExtractString(p, 'name')",
            _value_text(
                "if(JSONExtractRaw(p, 'arguments') IN ('', 'null'), '{}', JSONExtractRaw(p, 'arguments'))"
            ),
        )
        + ", arrayFilter(p -> JSONExtractString(p, 'type') = 'tool_call', "
        "JSONExtractArrayRaw(m, 'parts')), arrayEnumerate(arrayFilter(p -> JSONExtractString(p, 'type') = 'tool_call', JSONExtractArrayRaw(m, 'parts'))))",
    )
    result = _message(
        "'tool'",
        _value_text(
            "if(JSONExtractRaw(r, 'result') NOT IN ('', 'null'), JSONExtractRaw(r, 'result'), JSONExtractRaw(r, 'response'))"
        ),
        "JSONExtractString(r, 'id')",
    )
    return _bind(
        "r",
        "arrayFirst(p -> JSONExtractString(p, 'type') = 'tool_call_response', "
        "JSONExtractArrayRaw(m, 'parts'))",
        f"multiIf(r != '', {result}, JSONType(m, 'parts') = 'Array', {normal}, "
        + _message(
            "if(JSONExtractString(m, 'role') = '', 'user', JSONExtractString(m, 'role'))",
            _value_text(
                "if(JSONExtractRaw(m, 'content') IN ('', 'null'), m, JSONExtractRaw(m, 'content'))"
            ),
        )
        + ")",
    )


def _otel_sanitized() -> str:
    return _message(
        _value_text("JSONExtractRaw(m, 'role')"),
        "if(JSONType(m, 'content') IN ('String', 'Array'), "
        + _content_text("JSONExtractRaw(m, 'content')")
        + ", if(JSONExtractRaw(m, 'content') IN ('', 'null'), '', "
        + _json_stringify("JSONExtractRaw(m, 'content')")
        + "))",
        "JSONExtractString(m, 'tool_call_id')",
        "arrayMap(tc -> "
        + _tool(
            "JSONExtractString(tc, 'id')",
            "JSONExtractString(tc, 'function', 'name')",
            "JSONExtractString(tc, 'function', 'arguments')",
        )
        + ", JSONExtractArrayRaw(m, 'tool_calls'))",
    )


def _otel_messages() -> str:
    expand = (
        "multiIf(node.3, [node], JSONType(node.1) = 'Array', "
        "arrayMap(child -> tuple(child, node.2, JSONType(node.1, 1, 'parts') = 'Array'), JSONExtractArrayRaw(node.1)), "
        "JSONHas(node.1, 'role') AND JSONType(node.1, 'parts') != 'Array' AND JSONType(node.1, 'content') = 'Array', "
        "arrayMap(child -> tuple(__weave_last_turn_safe_json(JSONExtractRaw(child, 'text')), "
        + _value_text("JSONExtractRaw(node.1, 'role')")
        + ", false), JSONExtractArrayRaw(node.1, 'content')), [node])"
    )
    depth = (
        "arrayMax(arrayCumSum(arrayMap(t -> multiIf(t IN ('{', '['), 1, t IN ('}', ']'), -1, 0), "
        + _tokens("prompt")
        + ")))"
    )
    flattened = (
        f"arrayFold((nodes, level) -> arrayFlatten(arrayMap(node -> {expand}, nodes)), "
        f"range(toUInt64(greatest({depth}, 0)) + 1), [tuple(prompt, 'user', false)])"
    )
    terminal = _bind(
        "m",
        "node.1",
        "multiIf(node.3 OR (JSONHas(m, 'role') AND JSONType(m, 'parts') = 'Array'), "
        + _semconv_message()
        + ", JSONHas(m, 'role'), "
        + _otel_sanitized()
        + ", JSONType(m) = 'String', "
        + _plain_message("m", "node.2")
        + ", JSONHas(m, 'prompt'), "
        + _message("node.2", _value_text("JSONExtractRaw(m, 'prompt')"))
        + ", "
        + _message("node.2", _json_stringify("m"))
        + ")",
    )
    messages = (
        "if(JSONType(prompt, 'messages') = 'Array', arrayMap(m -> "
        + _otel_sanitized()
        + ", JSONExtractArrayRaw(prompt, 'messages')), arrayMap(node -> "
        + terminal
        + ", "
        + flattened
        + "))"
    )
    system = (
        "multiIf(JSONType(a, 'system') = 'String', JSONExtractString(a, 'system'), "
        "JSONType(a, 'system') = 'Array', arrayStringConcat(arrayMap(p -> JSONExtractString(p, 'content'), "
        "arrayFilter(p -> JSONExtractString(p, 'type') = 'text' AND JSONExtractString(p, 'content') != '', JSONExtractArrayRaw(a, 'system'))), '\\n'), "
        "JSONType(prompt, 'messages') = 'Array', "
        + _content_text("JSONExtractRaw(a, 'model_parameters', 'system')")
        + ", '')"
    )
    return _bind(
        "msgs",
        messages,
        "if("
        + _truthy("prompt")
        + ", "
        + _bind(
            "sys",
            system,
            "if(sys != '' AND NOT arrayExists(m -> m.1 = 'system', msgs), arrayConcat(["
            + _message("'system'", "sys")
            + "], msgs), msgs)",
        )
        + ", [])",
    )


def _adk_messages() -> str:
    tool = _tool(
        "JSONExtractString(p, 'function_call', 'id')",
        "JSONExtractString(p, 'function_call', 'name')",
        _json_stringify(
            "if("
            + _truthy("JSONExtractRaw(p, 'function_call', 'args')")
            + ", JSONExtractRaw(p, 'function_call', 'args'), '{}')"
        ),
    )
    message = _message(
        "multiIf(JSONExtractString(m, 'role') = 'model', 'assistant', JSONExtractString(m, 'role') != '', JSONExtractString(m, 'role'), 'user')",
        _text_blocks("JSONExtractRaw(m, 'parts')", predicate="JSONHas(p, 'text')"),
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
        + _bind(
            "msg",
            message,
            "if(msg.2 != '' OR notEmpty(msg.4) OR empty(JSONExtractArrayRaw(m, 'parts')), [msg], [])",
        )
        + "), JSONExtractArrayRaw(prompt, 'contents'))))"
    )


def _optional(
    obj: str, key: str, types: str, nullable: bool = True, path: tuple[str, ...] = ()
) -> str:
    allowed = f"{types}, 'Null'" if nullable else types
    keys = ", ".join(f"'{part}'" for part in (*path, key))
    return f"(NOT JSONHas({obj}, {keys}) OR JSONType({obj}, {keys}) IN ({allowed}))"


def _google_valid() -> str:
    part = " AND ".join(
        [
            "JSONType(p) = 'Object'",
            _optional("p", "text", "'String'"),
            "(JSONExtractRaw(p, 'functionCall') IN ('', 'null') OR (JSONType(p, 'functionCall') = 'Object' AND JSONType(p, 'functionCall', 'name') = 'String' AND "
            + _optional("p", "id", "'String'", path=("functionCall",))
            + " AND "
            + _optional("p", "args", "'Object'", path=("functionCall",))
            + "))",
            "(JSONExtractRaw(p, 'functionResponse') IN ('', 'null') OR (JSONType(p, 'functionResponse') = 'Object' AND "
            + _optional("p", "id", "'String'", path=("functionResponse",))
            + " AND "
            + _optional("p", "name", "'String'", path=("functionResponse",))
            + "))",
        ]
    )
    contents = (
        "JSONType(i, 'contents') = 'String' OR (JSONType(i, 'contents') = 'Array' AND arrayAll(c -> JSONType(c) = 'Object' AND JSONType(c, 'role') = 'String' AND (NOT JSONHas(c, 'parts') OR (JSONType(c, 'parts') = 'Array' AND arrayAll(p -> "
        + part
        + ", JSONExtractArrayRaw(c, 'parts')))), JSONExtractArrayRaw(i, 'contents')))"
    )
    config_valid = (
        "(JSONExtractRaw(i, 'config') IN ('', 'null') OR (JSONType(i, 'config') = 'Object' AND "
        + " AND ".join(
            [
                _optional("i", "systemInstruction", "'String'", path=("config",)),
                _optional("i", "responseMimeType", "'String'", path=("config",)),
                _optional(
                    "i", "temperature", "'Int64', 'UInt64', 'Float64'", path=("config",)
                ),
                _optional(
                    "i", "seed", "'Int64', 'UInt64', 'Float64'", path=("config",)
                ),
            ]
        )
        + "))"
    )
    self_valid = (
        "(JSONExtractRaw(i, 'self') IN ('', 'null') OR ("
        + _optional("i", "__class__", "'Object'", nullable=False, path=("self",))
        + " AND "
        + _optional("i", "GoogleGenAIai", "'Bool'", nullable=False, path=("self",))
        + " AND "
        + " AND ".join(
            _optional("i", key, "'String'", nullable=False, path=("self", "__class__"))
            for key in ("module", "qualname", "name")
        )
        + "))"
    )
    return (
        "JSONType(i, 'model') = 'String' AND ((JSONType(i, 'message') = 'String' AND JSONType(i, 'self', '__class__', 'module') = 'String' AND "
        + " AND ".join(
            _optional("i", key, "'String'", nullable=False, path=("self", "__class__"))
            for key in ("qualname", "name")
        )
        + ") OR (("
        + contents
        + ") AND "
        + config_valid
        + " AND "
        + _optional("i", "self", "'Object'")
        + " AND "
        + self_valid
        + "))"
    )


def _normalized_messages() -> str:
    raw_messages = _bind(
        "items",
        "JSONExtractArrayRaw(i, 'messages')",
        "arrayMap(m -> "
        + _raw_message()
        + ", if(JSONExtractString(items[-1], 'role') = 'tool', items, arraySlice(items, -1)))",
    )
    otel_key = (
        "arrayFirst(k -> JSONHas(i, k), ["
        + ", ".join(f"'{key}'" for key in INPUT_KEYS)
        + "])"
    )
    otel_output_key = (
        "arrayFirst(k -> JSONHas(o, k), ["
        + ", ".join(f"'{key}'" for key in OUTPUT_KEYS)
        + "])"
    )
    otel = _bind(
        "prompt",
        f"__weave_last_turn_safe_json(JSONExtractRaw(i, {otel_key}))",
        f"if(JSONHas(i, 'gcp.vertex.agent.llm_request') AND {_truthy('prompt')}, {_adk_messages()}, {_otel_messages()})",
    )
    responses = _bind(
        "msgs",
        _responses_messages(
            "if(JSONHas(i, 'input'), JSONExtractRaw(i, 'input'), JSONExtractRaw(i, 'messages'))"
        ),
        "if(JSONHas(i, 'instructions'), arrayConcat(["
        + _plain_field("i", "instructions")
        + "], msgs), msgs)",
    )
    google = _bind(
        "msgs",
        "multiIf(JSONType(i, 'message') = 'String', ["
        + _plain_field("i", "message")
        + "], JSONType(i, 'contents') = 'String', ["
        + _plain_field("i", "contents")
        + "], arrayMap(m -> "
        + _google_message()
        + ", JSONExtractArrayRaw(i, 'contents')))",
        "if(JSONType(i, 'message') != 'String' AND trimBoth(JSONExtractString(i, 'config', 'systemInstruction')) != '', arrayConcat(["
        + _plain_message("JSONExtractRaw(i, 'config', 'systemInstruction')", "'system'")
        + "], msgs), msgs)",
    )
    standard = _bind(
        "msgs",
        "arrayMap(m -> "
        + _standard_message()
        + ", JSONExtractArrayRaw(i, 'messages'))",
        "if(arrayAll(m -> JSONType(m, 'role') = 'String' OR arrayExists(p -> JSONExtractString(p, 'type') = 'tool_result' AND JSONHas(p, 'content') AND JSONHas(p, 'tool_use_id'), JSONExtractArrayRaw(m, 'content')), JSONExtractArrayRaw(i, 'messages')), "
        "if("
        + _truthy("JSONExtractRaw(i, 'system')")
        + ", arrayConcat(["
        + _message(
            "'system'",
            "if(JSONType(i, 'system') = 'Array', arrayStringConcat(arrayMap(p -> if(JSONType(p) = 'String', JSONExtractString(p), JSONExtractString(p, 'text')), arrayFilter(p -> JSONType(p) = 'String' OR JSONExtractString(p, 'type') = 'text', JSONExtractArrayRaw(i, 'system'))), '\\n\\n'), "
            + _content_text("JSONExtractRaw(i, 'system')")
            + ")",
        )
        + "], msgs), msgs), [])",
    )
    langchain_valid = "JSONType(i, 'messages', 1) = 'Array' AND arrayAll(m -> JSONType(m) = 'Object' AND JSONType(m, 'lc') IN ('Int64', 'UInt64', 'Float64') AND JSONExtractString(m, 'type') = 'constructor' AND JSONType(m, 'id') = 'Array' AND JSONType(m, 'kwargs') = 'Object', JSONExtractArrayRaw(i, 'messages', 1))"
    responses_valid = (
        "if(JSONType(i, 'messages') = 'Array', arrayAll(m -> "
        + _response_message_valid()
        + ", JSONExtractArrayRaw(i, 'messages')), JSONType(i, 'input') IN ('String', 'Array') AND JSONType(i, 'model') = 'String' AND JSONType(i, 'self') IN ('String', 'Object'))"
    )
    legacy = "JSONType(i, 'contents') = 'String' AND JSONExtractString(i, 'self', '__class__', 'module') = 'google.generativeai.generative_models'"
    generic = (
        "multiIf("
        + langchain_valid
        + ", arrayMap(m -> "
        + _langchain_message()
        + ", JSONExtractArrayRaw(i, 'messages', 1)), "
        + _google_valid()
        + ", "
        + google
        + ", "
        + legacy
        + ", if(JSONType(i, 'self', 'model_name') = 'String', ["
        + _plain_field("i", "contents")
        + "], []), "
        + responses_valid
        + ", "
        + responses
        + ", "
        "JSONType(i, 'prompt') = 'String' AND (position(JSONExtractString(i, 'model'), 'gpt-image') > 0 OR position(JSONExtractString(i, 'model'), 'dall-e') > 0 OR position(JSONExtractString(i, 'model'), 'dalle') > 0), ["
        + _plain_field("i", "prompt")
        + "], "
        "JSONType(i, 'messages') = 'Array', if(arrayExists(m -> arrayExists(p -> JSONType(p) = 'Null', JSONExtractArrayRaw(m, 'content')), JSONExtractArrayRaw(i, 'messages')), [], "
        + standard
        + "), [])"
    )
    invalid_output = "(JSONExtractString(o, 'object') = 'response' AND JSONType(o, 'output') != 'Array') OR (JSONExtractString(o, 'type') = 'message' AND JSONExtractString(o, 'role') = 'assistant' AND JSONType(o, 'model') = 'String' AND JSONType(o, 'content') = 'Array' AND arrayAll(p -> JSONExtractString(p, 'type') = 'text' AND JSONType(p, 'text') = 'String', JSONExtractArrayRaw(o, 'content')) AND JSONExtractRaw(o, 'usage') IN ('', 'null'))"
    source = (
        "multiIf(NOT "
        + _truthy("o")
        + " OR NOT "
        + _truthy("i")
        + ", "
        + raw_messages
        + ", "
        "arrayExists(m -> JSONType(m) = 'Null', JSONExtractArrayRaw(o, 'messages')), [], "
        "arrayExists(m -> JSONExtractString(m, 'role') = 'result' OR (JSONExtractString(m, 'role') = 'system' AND JSONExtractString(m, 'subtype') = 'init'), JSONExtractArrayRaw(o, 'messages')), "
        + _agent_messages("JSONExtractArrayRaw(o, 'messages')")
        + ", "
        "JSONExtractString(i, 'history', 1, 'role') = 'system' AND JSONExtractString(i, 'history', 1, 'subtype') = 'init', "
        "arrayConcat(if(JSONType(i, 'prompt') = 'String' AND JSONExtractString(i, 'prompt') != '', ["
        + _plain_field("i", "prompt")
        + "], []), "
        + _agent_messages("JSONExtractArrayRaw(i, 'history')")
        + "), "
        f"(JSONHas(a, 'otel_span') OR otel != '') AND (JSONExtractRaw(i, {otel_key}) NOT IN ('', 'null') OR JSONExtractRaw(o, {otel_output_key}) NOT IN ('', 'null')), {otel}, "
        + invalid_output
        + ", [], "
        "JSONType(i, 'prompt') = 'String' AND (position(JSONExtractString(i, 'model'), 'gpt-image') > 0 OR position(JSONExtractString(i, 'model'), 'dall-e') > 0 OR position(JSONExtractString(i, 'model'), 'dalle') > 0), ["
        + _plain_field("i", "prompt")
        + "], "
        + generic
        + ")"
    )
    return source


def _selected_message() -> str:
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
        "if(arrayExists(m -> isNull(m.2), trailing), NULL, "
        + _join(
            "arrayConcat("
            f"arrayMap(m -> {tool_text}, arrayMap(idx -> messages[idx], {invoking_indices})), "
            "arrayMap(m -> m.2, trailing))"
        )
        + ")",
    )
    single = _bind(
        "m",
        "messages[-1]",
        "if(isNull(m.2), NULL, " + _join(f"[m.2, {tool_text}]") + ")",
    )
    return f"if(messages[-1].1 = 'tool', {tool_group}, {single})"


def _projected_text() -> str:
    return (
        "if(isNull(selected), NULL, nullIf(arrayStringConcat(arrayMap((part, idx) -> "
        "if(idx % 2 = 1, part, multiIf(part = '', char(0), startsWith(part, 'P'), __weave_last_turn_pretty_json(base64Decode(substring(part, 2))), "
        "__weave_last_turn_json(base64Decode(substring(part, 2))))), splitByChar(char(0), assumeNotNull(selected)), "
        "arrayEnumerate(splitByChar(char(0), assumeNotNull(selected))))), ''))"
    )


def last_turn_from_sql(call_sql: str) -> str:
    """Evaluate each stage once; singleton ARRAY JOINs preserve call cardinality."""
    return f"""FROM (
        SELECT *, __weave_last_turn_safe_json(ifNull(__lt_inputs, '{{}}')) AS i,
            __weave_last_turn_safe_json(ifNull(__lt_output, 'null')) AS o,
            __weave_last_turn_safe_json(ifNull(__lt_attributes, '{{}}')) AS a,
            ifNull(__lt_otel, '') AS otel
        FROM ({call_sql})
    )
    ARRAY JOIN [{_prepare_json_reads(_normalized_messages())}] AS messages
    ARRAY JOIN [{_prepare_json_reads(_selected_message())}] AS selected
    ARRAY JOIN [{_projected_text()}] AS {LAST_TURN_COLUMN}"""

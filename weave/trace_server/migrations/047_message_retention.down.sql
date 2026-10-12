ALTER TABLE messages REMOVE TTL;

ALTER TABLE messages_mv_output_messages MODIFY QUERY
SELECT project_id,
       murmurHash3_128(m.2) AS content_digest,
       m.2 AS content,
       trace_id, span_id, parent_span_id,
       conversation_id, conversation_name, agent_name, agent_version,
       provider_name, request_model, operation_name,
       m.1 AS role,
       started_at,
       wb_user_id
FROM spans ARRAY JOIN output_messages AS m
WHERE m.2 != '';

ALTER TABLE messages_mv_input_messages MODIFY QUERY
SELECT project_id,
       murmurHash3_128(m.2) AS content_digest,
       m.2 AS content,
       trace_id, span_id, parent_span_id,
       conversation_id, conversation_name, agent_name, agent_version,
       provider_name, request_model, operation_name,
       m.1 AS role,
       started_at,
       wb_user_id
FROM spans ARRAY JOIN input_messages AS m
WHERE m.2 != '';

ALTER TABLE messages_mv_system_instructions MODIFY QUERY
SELECT project_id,
       murmurHash3_128(s) AS content_digest,
       s AS content,
       trace_id, span_id, parent_span_id,
       conversation_id, conversation_name, agent_name, agent_version,
       provider_name, request_model, operation_name,
       'system' AS role,
       started_at,
       wb_user_id
FROM spans ARRAY JOIN system_instructions AS s
WHERE s != '';

ALTER TABLE messages_mv_tool_call_arguments MODIFY QUERY
SELECT project_id,
       murmurHash3_128(tool_call_arguments) AS content_digest,
       tool_call_arguments AS content,
       trace_id, span_id, parent_span_id,
       conversation_id, conversation_name, agent_name, agent_version,
       provider_name, request_model, operation_name,
       'tool_call' AS role,
       started_at,
       wb_user_id
FROM spans
WHERE tool_call_arguments != '';

ALTER TABLE messages_mv_tool_call_result MODIFY QUERY
SELECT project_id,
       murmurHash3_128(tool_call_result) AS content_digest,
       tool_call_result AS content,
       trace_id, span_id, parent_span_id,
       conversation_id, conversation_name, agent_name, agent_version,
       provider_name, request_model, operation_name,
       'tool_result' AS role,
       started_at,
       wb_user_id
FROM spans
WHERE tool_call_result != '';

ALTER TABLE messages DROP COLUMN IF EXISTS expire_at;

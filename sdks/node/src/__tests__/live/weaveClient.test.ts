import {init, login} from '../../clientApi';
import {getWandbConfigs} from '../../wandb/settings';
import {vcrTest} from '../helpers/vcrTest';

async function authenticate() {
  const {apiKey} = getWandbConfigs();
  await login(apiKey ?? '');
}

describe('WeaveClient', () => {
  describe('getAgents', () => {
    vcrTest('gets agents', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgents();
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "agents": [
            {
              "agent_name": "my-cool-agent-with-attributes",
              "error_count": 0,
              "first_seen": "2026-06-15T21:32:12.358000",
              "invocation_count": 3,
              "last_seen": "2026-06-15T21:51:03.879000",
              "project_id": "drtangible-mocha/example",
              "span_count": 3,
              "total_duration_ms": 2,
              "total_input_tokens": 0,
              "total_output_tokens": 0,
            },
            {
              "agent_name": "my-cool-agent",
              "error_count": 0,
              "first_seen": "2026-06-15T20:37:39.749000",
              "invocation_count": 33,
              "last_seen": "2026-06-15T20:49:24.875000",
              "project_id": "drtangible-mocha/example",
              "span_count": 33,
              "total_duration_ms": 4,
              "total_input_tokens": 0,
              "total_output_tokens": 0,
            },
            {
              "agent_name": "Assistant",
              "error_count": 0,
              "first_seen": "2026-06-10T22:36:48.879000",
              "invocation_count": 5,
              "last_seen": "2026-06-10T22:39:35.019000",
              "project_id": "drtangible-mocha/example",
              "span_count": 5,
              "total_duration_ms": 9117,
              "total_input_tokens": 0,
              "total_output_tokens": 0,
            },
          ],
          "total_count": 3,
        }
      `);
    });

    vcrTest('supports limit and offset', async () => {
      await authenticate();
      const client = await init('example');

      let resp = await client.getAgents({limit: 1});
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "agents": [
            {
              "agent_name": "my-cool-agent-with-attributes",
              "error_count": 0,
              "first_seen": "2026-06-15T21:32:12.358000",
              "invocation_count": 3,
              "last_seen": "2026-06-15T21:51:03.879000",
              "project_id": "drtangible-mocha/example",
              "span_count": 3,
              "total_duration_ms": 2,
              "total_input_tokens": 0,
              "total_output_tokens": 0,
            },
          ],
          "total_count": 3,
        }
      `);

      resp = await client.getAgents({limit: 1, offset: 1});
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "agents": [
            {
              "agent_name": "my-cool-agent",
              "error_count": 0,
              "first_seen": "2026-06-15T20:37:39.749000",
              "invocation_count": 33,
              "last_seen": "2026-06-15T20:49:24.875000",
              "project_id": "drtangible-mocha/example",
              "span_count": 33,
              "total_duration_ms": 4,
              "total_input_tokens": 0,
              "total_output_tokens": 0,
            },
          ],
          "total_count": 3,
        }
      `);

      resp = await client.getAgents({limit: 1, offset: 2});
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "agents": [
            {
              "agent_name": "Assistant",
              "error_count": 0,
              "first_seen": "2026-06-10T22:36:48.879000",
              "invocation_count": 5,
              "last_seen": "2026-06-10T22:39:35.019000",
              "project_id": "drtangible-mocha/example",
              "span_count": 5,
              "total_duration_ms": 9117,
              "total_input_tokens": 0,
              "total_output_tokens": 0,
            },
          ],
          "total_count": 3,
        }
      `);

      resp = await client.getAgents({limit: 1, offset: 3});
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "agents": [],
          "total_count": 3,
        }
      `);
    });

    vcrTest('errors with invalid project id', async () => {
      await authenticate();
      const client = await init('nonexistent-project');

      expect(client.getAgents()).rejects.toMatchObject({
        data: null,
        error: {
          detail: 'Project not found',
        },
      });
    });
  });

  describe('getAgentVersions', () => {
    vcrTest('gets agent versions', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentVersions({agentName: 'my-cool-agent'});
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "total_count": 1,
          "versions": [
            {
              "agent_name": "my-cool-agent",
              "agent_version": "",
              "error_count": 0,
              "first_seen": "2026-06-15T20:37:39.749000",
              "invocation_count": 33,
              "last_seen": "2026-06-15T20:49:24.875000",
              "project_id": "drtangible-mocha/example",
              "span_count": 33,
              "total_duration_ms": 4,
              "total_input_tokens": 0,
              "total_output_tokens": 0,
            },
          ],
        }
      `);
    });

    vcrTest('supports limit and offset', async () => {
      await authenticate();
      const client = await init('example');

      let resp = await client.getAgentVersions({
        agentName: 'my-cool-agent',
        limit: 1,
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "total_count": 1,
          "versions": [
            {
              "agent_name": "my-cool-agent",
              "agent_version": "",
              "error_count": 0,
              "first_seen": "2026-06-15T20:37:39.749000",
              "invocation_count": 33,
              "last_seen": "2026-06-15T20:49:24.875000",
              "project_id": "drtangible-mocha/example",
              "span_count": 33,
              "total_duration_ms": 4,
              "total_input_tokens": 0,
              "total_output_tokens": 0,
            },
          ],
        }
      `);

      resp = await client.getAgentVersions({
        agentName: 'my-cool-agent',
        limit: 1,
        offset: 1,
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "total_count": 1,
          "versions": [],
        }
      `);
    });

    vcrTest('returns no versions for nonexistent agent', async () => {
      await authenticate();
      const client = await init('example');

      const resp = await client.getAgentVersions({
        agentName: 'some-nonexistent-agent',
        limit: 1,
      });

      expect(resp.data).toMatchInlineSnapshot(`
        {
          "total_count": 0,
          "versions": [],
        }
      `);
    });

    vcrTest('errors with invalid project id', async () => {
      await authenticate();
      const client = await init('nonexistent-project');

      expect(
        client.getAgentVersions({agentName: 'my-cool-agent'})
      ).rejects.toMatchObject({
        data: null,
        error: {
          detail: 'Project not found',
        },
      });
    });
  });

  describe('getAgentSpans', () => {
    vcrTest('gets agent spans', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentSpans({limit: 2});
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "groups": [],
          "spans": [
            {
              "agent_description": "",
              "agent_id": "",
              "agent_name": "",
              "agent_version": "",
              "artifact_refs": [],
              "cache_creation_input_tokens": 0,
              "cache_read_input_tokens": 0,
              "compaction_items_after": 0,
              "compaction_items_before": 0,
              "compaction_summary": null,
              "content_refs": [],
              "conversation_id": "trace_12de069f688c4095ab61bf21480e58b0",
              "conversation_name": "",
              "custom_attrs_bool": {},
              "custom_attrs_float": {},
              "custom_attrs_int": {},
              "custom_attrs_string": {},
              "ended_at": "2026-06-22T14:26:13.581000",
              "error_type": "",
              "finish_reasons": [],
              "input_messages": [],
              "input_tokens": 317,
              "object_refs": [],
              "operation_name": "chat",
              "output_messages": [],
              "output_tokens": 5,
              "output_type": "text",
              "parent_span_id": "8965f27f46ec6f92",
              "project_id": "drtangible-mocha/example",
              "provider_name": "openai",
              "raw_span_dump": null,
              "reasoning_content": null,
              "reasoning_tokens": 0,
              "request_choice_count": 0,
              "request_frequency_penalty": 0,
              "request_max_tokens": 0,
              "request_model": "gpt-5.4-mini-2026-03-17",
              "request_presence_penalty": 0,
              "request_seed": 0,
              "request_stop_sequences": [],
              "request_temperature": 0,
              "request_top_p": 0,
              "response_id": "resp_015daafad2bb2ddb006a394604edd481968554c54515495287",
              "response_model": "gpt-5.4-mini-2026-03-17",
              "server_address": "",
              "server_port": 0,
              "span_id": "9a7891fab09a59cb",
              "span_kind": "INTERNAL",
              "span_name": "chat gpt-5.4-mini-2026-03-17",
              "started_at": "2026-06-22T14:26:12.825000",
              "status_code": "UNSET",
              "status_message": "",
              "system_instructions": [],
              "tool_call_arguments": null,
              "tool_call_id": "",
              "tool_call_result": null,
              "tool_definitions": null,
              "tool_description": null,
              "tool_name": "",
              "tool_type": "",
              "trace_id": "1383ebb8471a2224318fcacadc9a2554",
              "wb_run_id": "",
              "wb_run_step": 0,
              "wb_run_step_end": 0,
              "wb_user_id": "VXNlcjo0MDQ5MTgy",
            },
            {
              "agent_description": "",
              "agent_id": "",
              "agent_name": "",
              "agent_version": "",
              "artifact_refs": [],
              "cache_creation_input_tokens": 0,
              "cache_read_input_tokens": 0,
              "compaction_items_after": 0,
              "compaction_items_before": 0,
              "compaction_summary": null,
              "content_refs": [],
              "conversation_id": "trace_12de069f688c4095ab61bf21480e58b0",
              "conversation_name": "",
              "custom_attrs_bool": {},
              "custom_attrs_float": {},
              "custom_attrs_int": {},
              "custom_attrs_string": {},
              "ended_at": "2026-06-22T14:26:12.824000",
              "error_type": "",
              "finish_reasons": [],
              "input_messages": [],
              "input_tokens": 0,
              "object_refs": [],
              "operation_name": "execute_tool",
              "output_messages": [],
              "output_tokens": 0,
              "output_type": "",
              "parent_span_id": "8965f27f46ec6f92",
              "project_id": "drtangible-mocha/example",
              "provider_name": "",
              "raw_span_dump": null,
              "reasoning_content": null,
              "reasoning_tokens": 0,
              "request_choice_count": 0,
              "request_frequency_penalty": 0,
              "request_max_tokens": 0,
              "request_model": "",
              "request_presence_penalty": 0,
              "request_seed": 0,
              "request_stop_sequences": [],
              "request_temperature": 0,
              "request_top_p": 0,
              "response_id": "",
              "response_model": "",
              "server_address": "",
              "server_port": 0,
              "span_id": "a86ca153cf785f21",
              "span_kind": "INTERNAL",
              "span_name": "execute_tool calculate",
              "started_at": "2026-06-22T14:26:12.824000",
              "status_code": "UNSET",
              "status_message": "",
              "system_instructions": [],
              "tool_call_arguments": null,
              "tool_call_id": "",
              "tool_call_result": null,
              "tool_definitions": null,
              "tool_description": null,
              "tool_name": "calculate",
              "tool_type": "",
              "trace_id": "1383ebb8471a2224318fcacadc9a2554",
              "wb_run_id": "",
              "wb_run_step": 0,
              "wb_run_step_end": 0,
              "wb_user_id": "VXNlcjo0MDQ5MTgy",
            },
          ],
          "total_count": 164,
        }
      `);
    });

    vcrTest('filters by agent name', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentSpans({
        agentName: 'my-cool-agent',
        limit: 2,
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "groups": [],
          "spans": [
            {
              "agent_description": "",
              "agent_id": "",
              "agent_name": "my-cool-agent",
              "agent_version": "",
              "artifact_refs": [],
              "cache_creation_input_tokens": 0,
              "cache_read_input_tokens": 0,
              "compaction_items_after": 0,
              "compaction_items_before": 0,
              "compaction_summary": null,
              "content_refs": [],
              "conversation_id": "019ecd0b-d38b-7079-ac31-ee541e48a389",
              "conversation_name": "",
              "custom_attrs_bool": {},
              "custom_attrs_float": {},
              "custom_attrs_int": {},
              "custom_attrs_string": {},
              "ended_at": "2026-06-15T20:49:24.875329",
              "error_type": "",
              "finish_reasons": [],
              "input_messages": [],
              "input_tokens": 0,
              "object_refs": [],
              "operation_name": "invoke_agent",
              "output_messages": [],
              "output_tokens": 0,
              "output_type": "",
              "parent_span_id": "",
              "project_id": "drtangible-mocha/example",
              "provider_name": "",
              "raw_span_dump": null,
              "reasoning_content": null,
              "reasoning_tokens": 0,
              "request_choice_count": 0,
              "request_frequency_penalty": 0,
              "request_max_tokens": 0,
              "request_model": "",
              "request_presence_penalty": 0,
              "request_seed": 0,
              "request_stop_sequences": [],
              "request_temperature": 0,
              "request_top_p": 0,
              "response_id": "",
              "response_model": "",
              "server_address": "",
              "server_port": 0,
              "span_id": "efbffb030cab41c9",
              "span_kind": "CLIENT",
              "span_name": "invoke_agent",
              "started_at": "2026-06-15T20:49:24.875000",
              "status_code": "UNSET",
              "status_message": "",
              "system_instructions": [],
              "tool_call_arguments": null,
              "tool_call_id": "",
              "tool_call_result": null,
              "tool_definitions": null,
              "tool_description": null,
              "tool_name": "",
              "tool_type": "",
              "trace_id": "a5a90a8d59e2c5e10f3ce5e69ba3c39a",
              "wb_run_id": "",
              "wb_run_step": 0,
              "wb_run_step_end": 0,
              "wb_user_id": "VXNlcjo0MDQ5MTgy",
            },
            {
              "agent_description": "",
              "agent_id": "",
              "agent_name": "my-cool-agent",
              "agent_version": "",
              "artifact_refs": [],
              "cache_creation_input_tokens": 0,
              "cache_read_input_tokens": 0,
              "compaction_items_after": 0,
              "compaction_items_before": 0,
              "compaction_summary": null,
              "content_refs": [],
              "conversation_id": "019ecd0b-d1c0-7fa7-bd22-85e31b44f90e",
              "conversation_name": "",
              "custom_attrs_bool": {},
              "custom_attrs_float": {},
              "custom_attrs_int": {},
              "custom_attrs_string": {},
              "ended_at": "2026-06-15T20:49:24.418812",
              "error_type": "",
              "finish_reasons": [],
              "input_messages": [],
              "input_tokens": 0,
              "object_refs": [],
              "operation_name": "invoke_agent",
              "output_messages": [],
              "output_tokens": 0,
              "output_type": "",
              "parent_span_id": "",
              "project_id": "drtangible-mocha/example",
              "provider_name": "",
              "raw_span_dump": null,
              "reasoning_content": null,
              "reasoning_tokens": 0,
              "request_choice_count": 0,
              "request_frequency_penalty": 0,
              "request_max_tokens": 0,
              "request_model": "",
              "request_presence_penalty": 0,
              "request_seed": 0,
              "request_stop_sequences": [],
              "request_temperature": 0,
              "request_top_p": 0,
              "response_id": "",
              "response_model": "",
              "server_address": "",
              "server_port": 0,
              "span_id": "68fa67d5baecc6ae",
              "span_kind": "CLIENT",
              "span_name": "invoke_agent",
              "started_at": "2026-06-15T20:49:24.418000",
              "status_code": "UNSET",
              "status_message": "",
              "system_instructions": [],
              "tool_call_arguments": null,
              "tool_call_id": "",
              "tool_call_result": null,
              "tool_definitions": null,
              "tool_description": null,
              "tool_name": "",
              "tool_type": "",
              "trace_id": "82a4727d59d526801594379ded785542",
              "wb_run_id": "",
              "wb_run_step": 0,
              "wb_run_step_end": 0,
              "wb_user_id": "VXNlcjo0MDQ5MTgy",
            },
          ],
          "total_count": 33,
        }
      `);
    });

    vcrTest('supports limit and offset', async () => {
      await authenticate();
      const client = await init('example');

      const first = await client.getAgentSpans({limit: 1});
      expect(first.data).toMatchInlineSnapshot(`
        {
          "groups": [],
          "spans": [
            {
              "agent_description": "",
              "agent_id": "",
              "agent_name": "",
              "agent_version": "",
              "artifact_refs": [],
              "cache_creation_input_tokens": 0,
              "cache_read_input_tokens": 0,
              "compaction_items_after": 0,
              "compaction_items_before": 0,
              "compaction_summary": null,
              "content_refs": [],
              "conversation_id": "trace_c50312356de3487fa90e381c9399b5b4",
              "conversation_name": "",
              "custom_attrs_bool": {},
              "custom_attrs_float": {},
              "custom_attrs_int": {},
              "custom_attrs_string": {},
              "ended_at": "2026-06-16T22:10:35.663000",
              "error_type": "",
              "finish_reasons": [],
              "input_messages": [],
              "input_tokens": 133,
              "object_refs": [],
              "operation_name": "chat",
              "output_messages": [],
              "output_tokens": 33,
              "output_type": "text",
              "parent_span_id": "c6153c0a6dc4010b",
              "project_id": "drtangible-mocha/example",
              "provider_name": "openai",
              "raw_span_dump": null,
              "reasoning_content": null,
              "reasoning_tokens": 0,
              "request_choice_count": 0,
              "request_frequency_penalty": 0,
              "request_max_tokens": 0,
              "request_model": "gpt-5.4-mini-2026-03-17",
              "request_presence_penalty": 0,
              "request_seed": 0,
              "request_stop_sequences": [],
              "request_temperature": 0,
              "request_top_p": 0,
              "response_id": "resp_0657da48080269b2006a31c9dabed48193a73f49a90ca3bf54",
              "response_model": "gpt-5.4-mini-2026-03-17",
              "server_address": "",
              "server_port": 0,
              "span_id": "53fc733e2f6b3417",
              "span_kind": "INTERNAL",
              "span_name": "chat gpt-5.4-mini-2026-03-17",
              "started_at": "2026-06-16T22:10:34.631000",
              "status_code": "UNSET",
              "status_message": "",
              "system_instructions": [],
              "tool_call_arguments": null,
              "tool_call_id": "",
              "tool_call_result": null,
              "tool_definitions": null,
              "tool_description": null,
              "tool_name": "",
              "tool_type": "",
              "trace_id": "86cc8e5a64b3bb1fbbf80cb377155950",
              "wb_run_id": "",
              "wb_run_step": 0,
              "wb_run_step_end": 0,
              "wb_user_id": "VXNlcjo0MDQ5MTgy",
            },
          ],
          "total_count": 146,
        }
      `);

      const second = await client.getAgentSpans({limit: 1, offset: 1});
      expect(second.data).toMatchInlineSnapshot(`
        {
          "groups": [],
          "spans": [
            {
              "agent_description": "",
              "agent_id": "",
              "agent_name": "Assistant",
              "agent_version": "",
              "artifact_refs": [],
              "cache_creation_input_tokens": 0,
              "cache_read_input_tokens": 0,
              "compaction_items_after": 0,
              "compaction_items_before": 0,
              "compaction_summary": null,
              "content_refs": [],
              "conversation_id": "trace_c50312356de3487fa90e381c9399b5b4",
              "conversation_name": "",
              "custom_attrs_bool": {},
              "custom_attrs_float": {},
              "custom_attrs_int": {},
              "custom_attrs_string": {},
              "ended_at": "2026-06-16T22:10:35.668000",
              "error_type": "",
              "finish_reasons": [],
              "input_messages": [],
              "input_tokens": 0,
              "object_refs": [],
              "operation_name": "invoke_agent",
              "output_messages": [],
              "output_tokens": 0,
              "output_type": "",
              "parent_span_id": "",
              "project_id": "drtangible-mocha/example",
              "provider_name": "openai",
              "raw_span_dump": null,
              "reasoning_content": null,
              "reasoning_tokens": 0,
              "request_choice_count": 0,
              "request_frequency_penalty": 0,
              "request_max_tokens": 0,
              "request_model": "",
              "request_presence_penalty": 0,
              "request_seed": 0,
              "request_stop_sequences": [],
              "request_temperature": 0,
              "request_top_p": 0,
              "response_id": "",
              "response_model": "",
              "server_address": "",
              "server_port": 0,
              "span_id": "c6153c0a6dc4010b",
              "span_kind": "INTERNAL",
              "span_name": "invoke_agent Assistant",
              "started_at": "2026-06-16T22:10:34.628000",
              "status_code": "UNSET",
              "status_message": "",
              "system_instructions": [],
              "tool_call_arguments": null,
              "tool_call_id": "",
              "tool_call_result": null,
              "tool_definitions": null,
              "tool_description": null,
              "tool_name": "",
              "tool_type": "",
              "trace_id": "86cc8e5a64b3bb1fbbf80cb377155950",
              "wb_run_id": "",
              "wb_run_step": 0,
              "wb_run_step_end": 0,
              "wb_user_id": "VXNlcjo0MDQ5MTgy",
            },
          ],
          "total_count": 146,
        }
      `);
    });

    vcrTest('returns no spans for nonexistent agent', async () => {
      await authenticate();
      const client = await init('example');

      const resp = await client.getAgentSpans({
        agentName: 'some-nonexistent-agent',
        limit: 5,
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "groups": [],
          "spans": [],
          "total_count": 0,
        }
      `);
    });

    vcrTest('errors with invalid project id', async () => {
      await authenticate();
      const client = await init('nonexistent-project');

      expect(client.getAgentSpans({limit: 5})).rejects.toMatchObject({
        data: null,
        error: {
          detail: 'Project not found',
        },
      });
    });
  });

  describe('getAgentTurn', () => {
    vcrTest('gets turn data for a given trace id', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentTurn({
        traceId: '86cc8e5a64b3bb1fbbf80cb377155950',
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "agent_name": "Assistant",
          "agent_version": "",
          "feedback": null,
          "messages": [
            {
              "agent_handoff": null,
              "agent_name": "User",
              "agent_start": null,
              "agent_version": null,
              "assistant_message": null,
              "context_compacted": null,
              "feedback": null,
              "span_id": null,
              "started_at": "2026-06-16T22:10:34.631000",
              "status_code": null,
              "tool_call": null,
              "type": "user_message",
              "user_message": {
                "content_refs": [],
                "text": "When was the last time Liverpool won the EPL?",
              },
            },
            {
              "agent_handoff": null,
              "agent_name": "Assistant",
              "agent_start": {
                "model": "",
                "status": "UNSET",
                "system_instructions": null,
                "tool_definitions": null,
              },
              "agent_version": "",
              "assistant_message": null,
              "context_compacted": null,
              "feedback": null,
              "span_id": "c6153c0a6dc4010b",
              "started_at": "2026-06-16T22:10:34.628000",
              "status_code": "UNSET",
              "tool_call": null,
              "type": "agent_start",
              "user_message": null,
            },
            {
              "agent_handoff": null,
              "agent_name": "Assistant",
              "agent_start": null,
              "agent_version": "",
              "assistant_message": {
                "content_refs": [],
                "duration_ms": 1032,
                "input_tokens": 133,
                "model": "gpt-5.4-mini-2026-03-17",
                "output_tokens": 33,
                "reasoning_content": "",
                "reasoning_tokens": 0,
                "status": "UNSET",
                "text": "Liverpool last won the English Premier League in the **2019–20 season**, clinching the title on **25 June 2020**.",
              },
              "context_compacted": null,
              "feedback": null,
              "span_id": "53fc733e2f6b3417",
              "started_at": "2026-06-16T22:10:34.631000",
              "status_code": "UNSET",
              "tool_call": null,
              "type": "assistant_message",
              "user_message": null,
            },
          ],
          "provider": "openai",
          "root_span_name": "Assistant",
          "status_code": "UNSET",
          "total_duration_ms": 1040,
          "trace_id": "86cc8e5a64b3bb1fbbf80cb377155950",
        }
      `);
    });

    vcrTest('includes feedback when requested', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentTurn({
        traceId: '86cc8e5a64b3bb1fbbf80cb377155950',
        includeFeedback: true,
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "agent_name": "Assistant",
          "agent_version": "",
          "feedback": [],
          "messages": [
            {
              "agent_handoff": null,
              "agent_name": "User",
              "agent_start": null,
              "agent_version": null,
              "assistant_message": null,
              "context_compacted": null,
              "feedback": null,
              "span_id": null,
              "started_at": "2026-06-16T22:10:34.631000",
              "status_code": null,
              "tool_call": null,
              "type": "user_message",
              "user_message": {
                "content_refs": [],
                "text": "When was the last time Liverpool won the EPL?",
              },
            },
            {
              "agent_handoff": null,
              "agent_name": "Assistant",
              "agent_start": {
                "model": "",
                "status": "UNSET",
                "system_instructions": null,
                "tool_definitions": null,
              },
              "agent_version": "",
              "assistant_message": null,
              "context_compacted": null,
              "feedback": null,
              "span_id": "c6153c0a6dc4010b",
              "started_at": "2026-06-16T22:10:34.628000",
              "status_code": "UNSET",
              "tool_call": null,
              "type": "agent_start",
              "user_message": null,
            },
            {
              "agent_handoff": null,
              "agent_name": "Assistant",
              "agent_start": null,
              "agent_version": "",
              "assistant_message": {
                "content_refs": [],
                "duration_ms": 1032,
                "input_tokens": 133,
                "model": "gpt-5.4-mini-2026-03-17",
                "output_tokens": 33,
                "reasoning_content": "",
                "reasoning_tokens": 0,
                "status": "UNSET",
                "text": "Liverpool last won the English Premier League in the **2019–20 season**, clinching the title on **25 June 2020**.",
              },
              "context_compacted": null,
              "feedback": null,
              "span_id": "53fc733e2f6b3417",
              "started_at": "2026-06-16T22:10:34.631000",
              "status_code": "UNSET",
              "tool_call": null,
              "type": "assistant_message",
              "user_message": null,
            },
          ],
          "provider": "openai",
          "root_span_name": "Assistant",
          "status_code": "UNSET",
          "total_duration_ms": 1040,
          "trace_id": "86cc8e5a64b3bb1fbbf80cb377155950",
        }
      `);
    });

    vcrTest('handles nonexistent trace id', async () => {
      await authenticate();
      const client = await init('example');

      const resp = await client.getAgentTurn({
        traceId: 'nonexistent-trace-id',
      });

      expect(resp.data).toMatchInlineSnapshot(`
        {
          "agent_name": null,
          "agent_version": null,
          "feedback": null,
          "messages": [],
          "provider": null,
          "root_span_name": null,
          "status_code": null,
          "total_duration_ms": null,
          "trace_id": "nonexistent-trace-id",
        }
      `);
    });

    vcrTest('errors with invalid project id', async () => {
      await authenticate();
      const client = await init('nonexistent-project');

      expect(
        client.getAgentTurn({
          traceId: '86cc8e5a64b3bb1fbbf80cb377155950',
        })
      ).rejects.toMatchObject({
        data: null,
        error: {
          detail: 'Project not found',
        },
      });
    });
  });

  describe('getAgentTurns', () => {
    vcrTest('gets turn data for the given conversation id', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentTurns({
        conversationId: 'trace_c50312356de3487fa90e381c9399b5b4',
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "conversation_id": "trace_c50312356de3487fa90e381c9399b5b4",
          "feedback": null,
          "has_more": false,
          "limit": 50,
          "offset": 0,
          "total_turns": 1,
          "turns": [
            {
              "agent_name": "Assistant",
              "agent_version": "",
              "feedback": null,
              "messages": [
                {
                  "agent_handoff": null,
                  "agent_name": "User",
                  "agent_start": null,
                  "agent_version": null,
                  "assistant_message": null,
                  "context_compacted": null,
                  "feedback": null,
                  "span_id": null,
                  "started_at": "2026-06-16T22:10:34.631000",
                  "status_code": null,
                  "tool_call": null,
                  "type": "user_message",
                  "user_message": {
                    "content_refs": [],
                    "text": "When was the last time Liverpool won the EPL?",
                  },
                },
                {
                  "agent_handoff": null,
                  "agent_name": "Assistant",
                  "agent_start": {
                    "model": "",
                    "status": "UNSET",
                    "system_instructions": null,
                    "tool_definitions": null,
                  },
                  "agent_version": "",
                  "assistant_message": null,
                  "context_compacted": null,
                  "feedback": null,
                  "span_id": "c6153c0a6dc4010b",
                  "started_at": "2026-06-16T22:10:34.628000",
                  "status_code": "UNSET",
                  "tool_call": null,
                  "type": "agent_start",
                  "user_message": null,
                },
                {
                  "agent_handoff": null,
                  "agent_name": "Assistant",
                  "agent_start": null,
                  "agent_version": "",
                  "assistant_message": {
                    "content_refs": [],
                    "duration_ms": 1032,
                    "input_tokens": 133,
                    "model": "gpt-5.4-mini-2026-03-17",
                    "output_tokens": 33,
                    "reasoning_content": "",
                    "reasoning_tokens": 0,
                    "status": "UNSET",
                    "text": "Liverpool last won the English Premier League in the **2019–20 season**, clinching the title on **25 June 2020**.",
                  },
                  "context_compacted": null,
                  "feedback": null,
                  "span_id": "53fc733e2f6b3417",
                  "started_at": "2026-06-16T22:10:34.631000",
                  "status_code": "UNSET",
                  "tool_call": null,
                  "type": "assistant_message",
                  "user_message": null,
                },
              ],
              "provider": "openai",
              "root_span_name": "Assistant",
              "status_code": "UNSET",
              "total_duration_ms": 1040,
              "trace_id": "86cc8e5a64b3bb1fbbf80cb377155950",
            },
          ],
        }
      `);
    });

    vcrTest('includes feedback when requested', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentTurns({
        conversationId: 'trace_c50312356de3487fa90e381c9399b5b4',
        includeFeedback: true,
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "conversation_id": "trace_c50312356de3487fa90e381c9399b5b4",
          "feedback": [],
          "has_more": false,
          "limit": 50,
          "offset": 0,
          "total_turns": 1,
          "turns": [
            {
              "agent_name": "Assistant",
              "agent_version": "",
              "feedback": [],
              "messages": [
                {
                  "agent_handoff": null,
                  "agent_name": "User",
                  "agent_start": null,
                  "agent_version": null,
                  "assistant_message": null,
                  "context_compacted": null,
                  "feedback": null,
                  "span_id": null,
                  "started_at": "2026-06-16T22:10:34.631000",
                  "status_code": null,
                  "tool_call": null,
                  "type": "user_message",
                  "user_message": {
                    "content_refs": [],
                    "text": "When was the last time Liverpool won the EPL?",
                  },
                },
                {
                  "agent_handoff": null,
                  "agent_name": "Assistant",
                  "agent_start": {
                    "model": "",
                    "status": "UNSET",
                    "system_instructions": null,
                    "tool_definitions": null,
                  },
                  "agent_version": "",
                  "assistant_message": null,
                  "context_compacted": null,
                  "feedback": null,
                  "span_id": "c6153c0a6dc4010b",
                  "started_at": "2026-06-16T22:10:34.628000",
                  "status_code": "UNSET",
                  "tool_call": null,
                  "type": "agent_start",
                  "user_message": null,
                },
                {
                  "agent_handoff": null,
                  "agent_name": "Assistant",
                  "agent_start": null,
                  "agent_version": "",
                  "assistant_message": {
                    "content_refs": [],
                    "duration_ms": 1032,
                    "input_tokens": 133,
                    "model": "gpt-5.4-mini-2026-03-17",
                    "output_tokens": 33,
                    "reasoning_content": "",
                    "reasoning_tokens": 0,
                    "status": "UNSET",
                    "text": "Liverpool last won the English Premier League in the **2019–20 season**, clinching the title on **25 June 2020**.",
                  },
                  "context_compacted": null,
                  "feedback": null,
                  "span_id": "53fc733e2f6b3417",
                  "started_at": "2026-06-16T22:10:34.631000",
                  "status_code": "UNSET",
                  "tool_call": null,
                  "type": "assistant_message",
                  "user_message": null,
                },
              ],
              "provider": "openai",
              "root_span_name": "Assistant",
              "status_code": "UNSET",
              "total_duration_ms": 1040,
              "trace_id": "86cc8e5a64b3bb1fbbf80cb377155950",
            },
          ],
        }
      `);
    });

    vcrTest('supports limit and offset', async () => {
      await authenticate();
      const client = await init('example');

      const first = await client.getAgentTurns({
        conversationId: 'trace_c50312356de3487fa90e381c9399b5b4',
        limit: 1,
      });
      expect(first.data).toMatchInlineSnapshot(`
        {
          "conversation_id": "trace_c50312356de3487fa90e381c9399b5b4",
          "feedback": null,
          "has_more": false,
          "limit": 1,
          "offset": 0,
          "total_turns": 1,
          "turns": [
            {
              "agent_name": "Assistant",
              "agent_version": "",
              "feedback": null,
              "messages": [
                {
                  "agent_handoff": null,
                  "agent_name": "User",
                  "agent_start": null,
                  "agent_version": null,
                  "assistant_message": null,
                  "context_compacted": null,
                  "feedback": null,
                  "span_id": null,
                  "started_at": "2026-06-16T22:10:34.631000",
                  "status_code": null,
                  "tool_call": null,
                  "type": "user_message",
                  "user_message": {
                    "content_refs": [],
                    "text": "When was the last time Liverpool won the EPL?",
                  },
                },
                {
                  "agent_handoff": null,
                  "agent_name": "Assistant",
                  "agent_start": {
                    "model": "",
                    "status": "UNSET",
                    "system_instructions": null,
                    "tool_definitions": null,
                  },
                  "agent_version": "",
                  "assistant_message": null,
                  "context_compacted": null,
                  "feedback": null,
                  "span_id": "c6153c0a6dc4010b",
                  "started_at": "2026-06-16T22:10:34.628000",
                  "status_code": "UNSET",
                  "tool_call": null,
                  "type": "agent_start",
                  "user_message": null,
                },
                {
                  "agent_handoff": null,
                  "agent_name": "Assistant",
                  "agent_start": null,
                  "agent_version": "",
                  "assistant_message": {
                    "content_refs": [],
                    "duration_ms": 1032,
                    "input_tokens": 133,
                    "model": "gpt-5.4-mini-2026-03-17",
                    "output_tokens": 33,
                    "reasoning_content": "",
                    "reasoning_tokens": 0,
                    "status": "UNSET",
                    "text": "Liverpool last won the English Premier League in the **2019–20 season**, clinching the title on **25 June 2020**.",
                  },
                  "context_compacted": null,
                  "feedback": null,
                  "span_id": "53fc733e2f6b3417",
                  "started_at": "2026-06-16T22:10:34.631000",
                  "status_code": "UNSET",
                  "tool_call": null,
                  "type": "assistant_message",
                  "user_message": null,
                },
              ],
              "provider": "openai",
              "root_span_name": "Assistant",
              "status_code": "UNSET",
              "total_duration_ms": 1040,
              "trace_id": "86cc8e5a64b3bb1fbbf80cb377155950",
            },
          ],
        }
      `);

      const second = await client.getAgentTurns({
        conversationId: 'trace_c50312356de3487fa90e381c9399b5b4',
        limit: 1,
        offset: 1,
      });
      expect(second.data).toMatchInlineSnapshot(`
        {
          "conversation_id": "trace_c50312356de3487fa90e381c9399b5b4",
          "feedback": null,
          "has_more": false,
          "limit": 1,
          "offset": 1,
          "total_turns": 1,
          "turns": [],
        }
      `);
    });

    vcrTest('handles nonexistent conversation id', async () => {
      await authenticate();
      const client = await init('example');

      const resp = await client.getAgentTurns({
        conversationId: 'nonexistent-conversation-id',
      });

      expect(resp.data).toMatchInlineSnapshot(`
        {
          "conversation_id": "nonexistent-conversation-id",
          "feedback": null,
          "has_more": false,
          "limit": 50,
          "offset": 0,
          "total_turns": 0,
          "turns": [],
        }
      `);
    });

    vcrTest('errors with invalid project id', async () => {
      await authenticate();
      const client = await init('nonexistent-project');

      expect(
        client.getAgentTurns({
          conversationId: 'trace_c50312356de3487fa90e381c9399b5b4',
        })
      ).rejects.toMatchObject({
        data: null,
        error: {
          detail: 'Project not found',
        },
      });
    });
  });

  describe('searchAgents', () => {
    vcrTest('searches messages by query', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.searchAgents({query: 'Liverpool', limit: 2});
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "results": [
            {
              "agent_name": "",
              "conversation_id": "trace_c50312356de3487fa90e381c9399b5b4",
              "conversation_name": "",
              "last_activity": "2026-06-16T22:10:34.631000",
              "matched_messages": [
                {
                  "content_digest": "32cce4db16007e3f5c876c1a4b91e930",
                  "content_preview": "[{"type": "text", "content": "When was the last time Liverpool won the EPL?"}]",
                  "role": "user",
                  "span_id": "53fc733e2f6b3417",
                  "started_at": "2026-06-16T22:10:34.631000",
                  "trace_id": "86cc8e5a64b3bb1fbbf80cb377155950",
                },
                {
                  "content_digest": "95fbc841becb3025395d9f997712ad53",
                  "content_preview": "[{"type": "text", "content": "Liverpool last won the English Premier League in the **2019\\u201320 season**, clinching the title on **25 June 2020**."}]",
                  "role": "assistant",
                  "span_id": "53fc733e2f6b3417",
                  "started_at": "2026-06-16T22:10:34.631000",
                  "trace_id": "86cc8e5a64b3bb1fbbf80cb377155950",
                },
              ],
            },
          ],
          "total_conversations": 1,
        }
      `);
    });

    vcrTest('filters by agent name', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.searchAgents({
        query: '',
        agentName: 'Assistant',
        limit: 2,
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "results": [
            {
              "agent_name": "Assistant",
              "conversation_id": "trace_1f21f184e99b4448bb6ac166e0a7191a",
              "conversation_name": "",
              "last_activity": "2026-06-18T20:52:22.517000",
              "matched_messages": [
                {
                  "content_digest": "6eeb22f6a15d0bde7701fb1788261ed9",
                  "content_preview": "[{"type": "tool_call", "toolName": "calculate", "arguments": "{\\"expression\\":\\"(17 * 4) + 93\\"}"}]",
                  "role": "assistant",
                  "span_id": "6f2673e3edec2637",
                  "started_at": "2026-06-18T20:52:22.517000",
                  "trace_id": "7aa79afa1e0427550fcaaed601089221",
                },
                {
                  "content_digest": "47023b151742ce5a5875efc8bba23ca4",
                  "content_preview": "[{"type": "text", "content": "What is (17 * 4) + 93?"}]",
                  "role": "user",
                  "span_id": "6f2673e3edec2637",
                  "started_at": "2026-06-18T20:52:22.517000",
                  "trace_id": "7aa79afa1e0427550fcaaed601089221",
                },
              ],
            },
          ],
          "total_conversations": 1,
        }
      `);
    });

    vcrTest('filters by conversation id', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.searchAgents({
        query: '',
        conversationId: 'trace_c50312356de3487fa90e381c9399b5b4',
        limit: 2,
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "results": [
            {
              "agent_name": "",
              "conversation_id": "trace_c50312356de3487fa90e381c9399b5b4",
              "conversation_name": "",
              "last_activity": "2026-06-16T22:10:34.631000",
              "matched_messages": [
                {
                  "content_digest": "32cce4db16007e3f5c876c1a4b91e930",
                  "content_preview": "[{"type": "text", "content": "When was the last time Liverpool won the EPL?"}]",
                  "role": "user",
                  "span_id": "53fc733e2f6b3417",
                  "started_at": "2026-06-16T22:10:34.631000",
                  "trace_id": "86cc8e5a64b3bb1fbbf80cb377155950",
                },
                {
                  "content_digest": "95fbc841becb3025395d9f997712ad53",
                  "content_preview": "[{"type": "text", "content": "Liverpool last won the English Premier League in the **2019\\u201320 season**, clinching the title on **25 June 2020**."}]",
                  "role": "assistant",
                  "span_id": "53fc733e2f6b3417",
                  "started_at": "2026-06-16T22:10:34.631000",
                  "trace_id": "86cc8e5a64b3bb1fbbf80cb377155950",
                },
              ],
            },
          ],
          "total_conversations": 1,
        }
      `);
    });

    vcrTest('filters by trace id', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.searchAgents({
        query: '',
        traceId: '86cc8e5a64b3bb1fbbf80cb377155950',
        limit: 2,
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "results": [
            {
              "agent_name": "",
              "conversation_id": "trace_c50312356de3487fa90e381c9399b5b4",
              "conversation_name": "",
              "last_activity": "2026-06-16T22:10:34.631000",
              "matched_messages": [
                {
                  "content_digest": "32cce4db16007e3f5c876c1a4b91e930",
                  "content_preview": "[{"type": "text", "content": "When was the last time Liverpool won the EPL?"}]",
                  "role": "user",
                  "span_id": "53fc733e2f6b3417",
                  "started_at": "2026-06-16T22:10:34.631000",
                  "trace_id": "86cc8e5a64b3bb1fbbf80cb377155950",
                },
                {
                  "content_digest": "95fbc841becb3025395d9f997712ad53",
                  "content_preview": "[{"type": "text", "content": "Liverpool last won the English Premier League in the **2019\\u201320 season**, clinching the title on **25 June 2020**."}]",
                  "role": "assistant",
                  "span_id": "53fc733e2f6b3417",
                  "started_at": "2026-06-16T22:10:34.631000",
                  "trace_id": "86cc8e5a64b3bb1fbbf80cb377155950",
                },
              ],
            },
          ],
          "total_conversations": 1,
        }
      `);
    });

    vcrTest('supports limit and offset', async () => {
      await authenticate();
      const client = await init('example');

      const first = await client.searchAgents({query: '', limit: 1});
      expect(first.data).toMatchInlineSnapshot(`
        {
          "results": [
            {
              "agent_name": "claude_agent_sdk",
              "conversation_id": "bf0914f2-a124-4da7-927d-61e463a70cba",
              "conversation_name": "",
              "last_activity": "2026-06-25T17:35:02.387000",
              "matched_messages": [
                {
                  "content_digest": "e37f4a8d973198d2a9c83918a3ee2712",
                  "content_preview": "[{"type": "text", "content": "Weave is an observability and tracing SDK for LLM applications with Python and TypeScript/Node implementations that automatically instruments AI integrations (OpenAI, Anthropic, etc.) and stores trace data in a ClickHouse-backed trace server."}]",
                  "role": "assistant",
                  "span_id": "025fb68b7d6a1a1b",
                  "started_at": "2026-06-25T17:35:02.387000",
                  "trace_id": "4a816ff61e80c6389ce60f9167e259cb",
                },
              ],
            },
          ],
          "total_conversations": 1,
        }
      `);

      const second = await client.searchAgents({
        query: '',
        limit: 1,
        offset: 1,
      });
      expect(second.data).toMatchInlineSnapshot(`
        {
          "results": [
            {
              "agent_name": "claude_agent_sdk",
              "conversation_id": "bf0914f2-a124-4da7-927d-61e463a70cba",
              "conversation_name": "",
              "last_activity": "2026-06-25T17:35:00.987000",
              "matched_messages": [
                {
                  "content_digest": "f050523d075a22a6c93dc28715ee4e91",
                  "content_preview": "[{"type": "reasoning", "content": "The user is asking me to summarize what I learned about the project in one sentence. Let me think about what I've learned:\\n\\n1. This is the Weave repository - a tracing/observability SDK for AI/LLM applications\\n2. It has both Python and TypeScript/Node implementations\\n3. The Node SDK is in \`sdks/node\` and uses pnpm for package management\\n4. The largest TypeScript file is a generated API client (8,225 lines) for the trace server\\n5. It supports automatic int",
                  "role": "assistant",
                  "span_id": "35494d9c72f42040",
                  "started_at": "2026-06-25T17:35:00.987000",
                  "trace_id": "4a816ff61e80c6389ce60f9167e259cb",
                },
              ],
            },
          ],
          "total_conversations": 1,
        }
      `);
    });

    vcrTest('returns no results for nonexistent query', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.searchAgents({
        query: 'zzz-no-such-text-anywhere-in-this-project-zzz',
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "results": [],
          "total_conversations": 0,
        }
      `);
    });

    vcrTest('errors with invalid project id', async () => {
      await authenticate();
      const client = await init('nonexistent-project');

      expect(client.searchAgents({query: ''})).rejects.toMatchObject({
        data: null,
        error: {
          detail: 'Project not found',
        },
      });
    });
  });

  describe('getAgentSpanStats', () => {
    vcrTest('gets span stats over a time window', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentSpanStats({
        start: '2026-06-10T00:00:00Z',
        end: '2026-06-23T00:00:00Z',
        metrics: [
          {
            alias: 'total_input_tokens',
            value_type: 'number',
            aggregations: ['sum'],
            value: {source: 'field', key: 'input_tokens'},
          },
        ],
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "bucket_type": "time",
          "columns": [
            {
              "aggregation": null,
              "metric": null,
              "name": "timestamp",
              "role": "time",
              "value_type": "datetime",
            },
            {
              "aggregation": "sum",
              "metric": "total_input_tokens",
              "name": "sum_total_input_tokens",
              "role": "metric",
              "value_type": "number",
            },
          ],
          "end": "2026-06-23T00:00:00Z",
          "granularity": 43200,
          "rows": [
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-10T00:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-10T12:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-11T00:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-11T12:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-12T00:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-12T12:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-13T00:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-13T12:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-14T00:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-14T12:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-15T00:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-15T12:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-16T00:00:00",
            },
            {
              "sum_total_input_tokens": 2030,
              "timestamp": "2026-06-16T12:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-17T00:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-17T12:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-18T00:00:00",
            },
            {
              "sum_total_input_tokens": 951,
              "timestamp": "2026-06-18T12:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-19T00:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-19T12:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-20T00:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-20T12:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-21T00:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-21T12:00:00",
            },
            {
              "sum_total_input_tokens": 0,
              "timestamp": "2026-06-22T00:00:00",
            },
            {
              "sum_total_input_tokens": 2853,
              "timestamp": "2026-06-22T12:00:00",
            },
          ],
          "start": "2026-06-10T00:00:00Z",
          "timezone": "UTC",
        }
      `);
    });

    vcrTest('bucketed by time granularity', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentSpanStats({
        start: '2026-06-10T00:00:00Z',
        end: '2026-06-23T00:00:00Z',
        granularity: 86400,
        metrics: [
          {
            alias: 'span_count',
            value_type: 'string',
            aggregations: ['count'],
            value: {source: 'field', key: 'span_id'},
          },
        ],
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "bucket_type": "time",
          "columns": [
            {
              "aggregation": null,
              "metric": null,
              "name": "timestamp",
              "role": "time",
              "value_type": "datetime",
            },
            {
              "aggregation": "count",
              "metric": "span_count",
              "name": "count_span_count",
              "role": "metric",
              "value_type": "number",
            },
          ],
          "end": "2026-06-23T00:00:00Z",
          "granularity": 86400,
          "rows": [
            {
              "count_span_count": 15,
              "timestamp": "2026-06-10T00:00:00",
            },
            {
              "count_span_count": 0,
              "timestamp": "2026-06-11T00:00:00",
            },
            {
              "count_span_count": 0,
              "timestamp": "2026-06-12T00:00:00",
            },
            {
              "count_span_count": 0,
              "timestamp": "2026-06-13T00:00:00",
            },
            {
              "count_span_count": 0,
              "timestamp": "2026-06-14T00:00:00",
            },
            {
              "count_span_count": 111,
              "timestamp": "2026-06-15T00:00:00",
            },
            {
              "count_span_count": 20,
              "timestamp": "2026-06-16T00:00:00",
            },
            {
              "count_span_count": 0,
              "timestamp": "2026-06-17T00:00:00",
            },
            {
              "count_span_count": 9,
              "timestamp": "2026-06-18T00:00:00",
            },
            {
              "count_span_count": 0,
              "timestamp": "2026-06-19T00:00:00",
            },
            {
              "count_span_count": 0,
              "timestamp": "2026-06-20T00:00:00",
            },
            {
              "count_span_count": 0,
              "timestamp": "2026-06-21T00:00:00",
            },
            {
              "count_span_count": 27,
              "timestamp": "2026-06-22T00:00:00",
            },
          ],
          "start": "2026-06-10T00:00:00Z",
          "timezone": "UTC",
        }
      `);
    });

    vcrTest('returns empty rows for a window with no data', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentSpanStats({
        start: '2000-01-01T00:00:00Z',
        end: '2000-01-02T00:00:00Z',
        metrics: [
          {
            alias: 'span_count',
            value_type: 'string',
            aggregations: ['count'],
            value: {source: 'field', key: 'span_id'},
          },
        ],
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "bucket_type": "time",
          "columns": [
            {
              "aggregation": null,
              "metric": null,
              "name": "timestamp",
              "role": "time",
              "value_type": "datetime",
            },
            {
              "aggregation": "count",
              "metric": "span_count",
              "name": "count_span_count",
              "role": "metric",
              "value_type": "number",
            },
          ],
          "end": "2000-01-02T00:00:00Z",
          "granularity": 21600,
          "rows": [
            {
              "count_span_count": 0,
              "timestamp": "2000-01-01T00:00:00",
            },
            {
              "count_span_count": 0,
              "timestamp": "2000-01-01T06:00:00",
            },
            {
              "count_span_count": 0,
              "timestamp": "2000-01-01T12:00:00",
            },
            {
              "count_span_count": 0,
              "timestamp": "2000-01-01T18:00:00",
            },
          ],
          "start": "2000-01-01T00:00:00Z",
          "timezone": "UTC",
        }
      `);
    });

    vcrTest('errors with invalid project id', async () => {
      await authenticate();
      const client = await init('nonexistent-project');

      expect(
        client.getAgentSpanStats({
          start: '2026-06-10T00:00:00Z',
          end: '2026-06-23T00:00:00Z',
          metrics: [
            {
              alias: 'total_input_tokens',
              value_type: 'number',
              aggregations: ['sum'],
              value: {source: 'field', key: 'input_tokens'},
            },
          ],
        })
      ).rejects.toMatchObject({
        data: null,
        error: {
          detail: 'Project not found',
        },
      });
    });
  });

  describe('getAgentCustomAttrsSchema', () => {
    vcrTest('gets the custom attrs schema for the project', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentCustomAttrsSchema({});
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "attributes": [
            {
              "key": "gen_ai.tool.call.arguments.city",
              "source": "custom_attrs_string",
              "span_count": 84,
              "value_type": "string",
            },
            {
              "key": "gen_ai.tool.call.result.condition",
              "source": "custom_attrs_string",
              "span_count": 72,
              "value_type": "string",
            },
            {
              "key": "gen_ai.tool.call.result.temp",
              "source": "custom_attrs_int",
              "span_count": 72,
              "value_type": "int",
            },
            {
              "key": "weave.openai_agents.span_id",
              "source": "custom_attrs_string",
              "span_count": 56,
              "value_type": "string",
            },
            {
              "key": "weave.openai_agents.trace_id",
              "source": "custom_attrs_string",
              "span_count": 56,
              "value_type": "string",
            },
            {
              "key": "gen_ai.tool.call.arguments.expression",
              "source": "custom_attrs_string",
              "span_count": 30,
              "value_type": "string",
            },
            {
              "key": "integration.meta.package_name",
              "source": "custom_attrs_string",
              "span_count": 22,
              "value_type": "string",
            },
            {
              "key": "integration.name",
              "source": "custom_attrs_string",
              "span_count": 22,
              "value_type": "string",
            },
            {
              "key": "integration.version",
              "source": "custom_attrs_string",
              "span_count": 22,
              "value_type": "string",
            },
            {
              "key": "weave.openai_agents.agent.output_type",
              "source": "custom_attrs_string",
              "span_count": 13,
              "value_type": "string",
            },
            {
              "key": "weave.openai_agents.agent.tools",
              "source": "custom_attrs_string",
              "span_count": 13,
              "value_type": "string",
            },
            {
              "key": "gen_ai.tool.call.arguments.unit",
              "source": "custom_attrs_string",
              "span_count": 12,
              "value_type": "string",
            },
            {
              "key": "weave.another",
              "source": "custom_attrs_int",
              "span_count": 6,
              "value_type": "int",
            },
            {
              "key": "weave.something",
              "source": "custom_attrs_string",
              "span_count": 6,
              "value_type": "string",
            },
            {
              "key": "weave.tag",
              "source": "custom_attrs_string",
              "span_count": 6,
              "value_type": "string",
            },
            {
              "key": "claude_agent_sdk.num_turns",
              "source": "custom_attrs_int",
              "span_count": 3,
              "value_type": "int",
            },
            {
              "key": "claude_agent_sdk.usage.cost_usd",
              "source": "custom_attrs_float",
              "span_count": 3,
              "value_type": "float",
            },
            {
              "key": "gen_ai.usage.total_tokens",
              "source": "custom_attrs_int",
              "span_count": 3,
              "value_type": "int",
            },
            {
              "key": "gen_ai.tool.call.arguments.pattern",
              "source": "custom_attrs_string",
              "span_count": 2,
              "value_type": "string",
            },
            {
              "key": "gen_ai.tool.call.arguments.command",
              "source": "custom_attrs_string",
              "span_count": 1,
              "value_type": "string",
            },
            {
              "key": "gen_ai.tool.call.arguments.description",
              "source": "custom_attrs_string",
              "span_count": 1,
              "value_type": "string",
            },
            {
              "key": "gen_ai.tool.call.arguments.file_path",
              "source": "custom_attrs_string",
              "span_count": 1,
              "value_type": "string",
            },
            {
              "key": "gen_ai.tool.call.arguments.limit",
              "source": "custom_attrs_int",
              "span_count": 1,
              "value_type": "int",
            },
          ],
          "has_more": false,
          "limit": 200,
          "offset": 0,
        }
      `);
    });

    vcrTest('filters by time window', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentCustomAttrsSchema({
        startedAfter: '2026-06-15T00:00:00Z',
        startedBefore: '2026-06-23T00:00:00Z',
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "attributes": [
            {
              "key": "weave.openai_agents.span_id",
              "source": "custom_attrs_string",
              "span_count": 56,
              "value_type": "string",
            },
            {
              "key": "weave.openai_agents.trace_id",
              "source": "custom_attrs_string",
              "span_count": 56,
              "value_type": "string",
            },
            {
              "key": "weave.openai_agents.agent.output_type",
              "source": "custom_attrs_string",
              "span_count": 13,
              "value_type": "string",
            },
            {
              "key": "weave.openai_agents.agent.tools",
              "source": "custom_attrs_string",
              "span_count": 13,
              "value_type": "string",
            },
            {
              "key": "gen_ai.tool.call.arguments.city",
              "source": "custom_attrs_string",
              "span_count": 12,
              "value_type": "string",
            },
            {
              "key": "gen_ai.tool.call.arguments.unit",
              "source": "custom_attrs_string",
              "span_count": 12,
              "value_type": "string",
            },
            {
              "key": "gen_ai.tool.call.arguments.expression",
              "source": "custom_attrs_string",
              "span_count": 6,
              "value_type": "string",
            },
            {
              "key": "weave.another",
              "source": "custom_attrs_int",
              "span_count": 6,
              "value_type": "int",
            },
            {
              "key": "weave.something",
              "source": "custom_attrs_string",
              "span_count": 6,
              "value_type": "string",
            },
            {
              "key": "weave.tag",
              "source": "custom_attrs_string",
              "span_count": 6,
              "value_type": "string",
            },
          ],
          "has_more": false,
          "limit": 200,
          "offset": 0,
        }
      `);
    });

    vcrTest('filters by query', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentCustomAttrsSchema({
        query: {
          $expr: {
            $eq: [
              {$getField: 'agent_name'},
              {$literal: 'my-cool-agent-with-attributes'},
            ],
          },
        },
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "attributes": [
            {
              "key": "weave.another",
              "source": "custom_attrs_int",
              "span_count": 2,
              "value_type": "int",
            },
            {
              "key": "weave.something",
              "source": "custom_attrs_string",
              "span_count": 2,
              "value_type": "string",
            },
            {
              "key": "weave.tag",
              "source": "custom_attrs_string",
              "span_count": 2,
              "value_type": "string",
            },
          ],
          "has_more": false,
          "limit": 200,
          "offset": 0,
        }
      `);
    });

    vcrTest('supports limit and offset', async () => {
      await authenticate();
      const client = await init('example');

      const first = await client.getAgentCustomAttrsSchema({limit: 1});
      expect(first.data).toMatchInlineSnapshot(`
        {
          "attributes": [
            {
              "key": "gen_ai.tool.call.arguments.city",
              "source": "custom_attrs_string",
              "span_count": 84,
              "value_type": "string",
            },
          ],
          "has_more": true,
          "limit": 1,
          "offset": 0,
        }
      `);

      const second = await client.getAgentCustomAttrsSchema({
        limit: 1,
        offset: 1,
      });
      expect(second.data).toMatchInlineSnapshot(`
        {
          "attributes": [
            {
              "key": "gen_ai.tool.call.result.condition",
              "source": "custom_attrs_string",
              "span_count": 72,
              "value_type": "string",
            },
          ],
          "has_more": true,
          "limit": 1,
          "offset": 1,
        }
      `);
    });

    vcrTest('returns no attributes for a window with no data', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentCustomAttrsSchema({
        startedAfter: '2000-01-01T00:00:00Z',
        startedBefore: '2000-01-02T00:00:00Z',
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "attributes": [],
          "has_more": false,
          "limit": 200,
          "offset": 0,
        }
      `);
    });

    vcrTest('errors with invalid project id', async () => {
      await authenticate();
      const client = await init('nonexistent-project');

      expect(client.getAgentCustomAttrsSchema({})).rejects.toMatchObject({
        data: null,
        error: {
          detail: 'Project not found',
        },
      });
    });
  });
});

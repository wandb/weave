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
      const resp = await client.getAgentSpans({limit: 5});
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
              "conversation_id": "trace_a6fe0c92ca474ed0bd068c531f7af12c",
              "conversation_name": "",
              "custom_attrs_bool": {},
              "custom_attrs_float": {},
              "custom_attrs_int": {},
              "custom_attrs_string": {},
              "ended_at": "2026-06-16T22:10:17.148000",
              "error_type": "",
              "finish_reasons": [],
              "input_messages": [],
              "input_tokens": 315,
              "object_refs": [],
              "operation_name": "chat",
              "output_messages": [],
              "output_tokens": 5,
              "output_type": "text",
              "parent_span_id": "5e8f4a2c79a1f294",
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
              "response_id": "resp_05df0edbb72736f5006a31c9c876a481938cdd07481ee2b33e",
              "response_model": "gpt-5.4-mini-2026-03-17",
              "server_address": "",
              "server_port": 0,
              "span_id": "46b56d77a8411c2d",
              "span_kind": "INTERNAL",
              "span_name": "chat gpt-5.4-mini-2026-03-17",
              "started_at": "2026-06-16T22:10:16.373000",
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
              "trace_id": "67648280e1e0dffe7e560df171d99ddc",
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
              "conversation_id": "trace_a6fe0c92ca474ed0bd068c531f7af12c",
              "conversation_name": "",
              "custom_attrs_bool": {},
              "custom_attrs_float": {},
              "custom_attrs_int": {},
              "custom_attrs_string": {},
              "ended_at": "2026-06-16T22:10:16.372000",
              "error_type": "",
              "finish_reasons": [],
              "input_messages": [],
              "input_tokens": 0,
              "object_refs": [],
              "operation_name": "execute_tool",
              "output_messages": [],
              "output_tokens": 0,
              "output_type": "",
              "parent_span_id": "5e8f4a2c79a1f294",
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
              "span_id": "054c43c9f804e63e",
              "span_kind": "INTERNAL",
              "span_name": "execute_tool calculate",
              "started_at": "2026-06-16T22:10:16.371000",
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
              "trace_id": "67648280e1e0dffe7e560df171d99ddc",
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
              "conversation_id": "trace_a6fe0c92ca474ed0bd068c531f7af12c",
              "conversation_name": "",
              "custom_attrs_bool": {},
              "custom_attrs_float": {},
              "custom_attrs_int": {},
              "custom_attrs_string": {},
              "ended_at": "2026-06-16T22:10:16.371000",
              "error_type": "",
              "finish_reasons": [],
              "input_messages": [],
              "input_tokens": 268,
              "object_refs": [],
              "operation_name": "chat",
              "output_messages": [],
              "output_tokens": 25,
              "output_type": "text",
              "parent_span_id": "5e8f4a2c79a1f294",
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
              "response_id": "resp_05df0edbb72736f5006a31c9c767b88193ad36aca93bbe7116",
              "response_model": "gpt-5.4-mini-2026-03-17",
              "server_address": "",
              "server_port": 0,
              "span_id": "00a5ca1e03e154e5",
              "span_kind": "INTERNAL",
              "span_name": "chat gpt-5.4-mini-2026-03-17",
              "started_at": "2026-06-16T22:10:15.298000",
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
              "trace_id": "67648280e1e0dffe7e560df171d99ddc",
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

    vcrTest('filters by agent name', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentSpans({
        agentName: 'my-cool-agent',
        limit: 5,
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
              "conversation_id": "019ecd0b-7454-7c08-b475-e6b43eb52c42",
              "conversation_name": "",
              "custom_attrs_bool": {},
              "custom_attrs_float": {},
              "custom_attrs_int": {},
              "custom_attrs_string": {},
              "ended_at": "2026-06-15T20:49:00.500173",
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
              "span_id": "9f9ad6d4a2cc4404",
              "span_kind": "CLIENT",
              "span_name": "invoke_agent",
              "started_at": "2026-06-15T20:49:00.500000",
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
              "trace_id": "50e37adb3562038efdac9f30ef21024f",
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
              "conversation_id": "019ecd0b-71aa-787e-aec0-aae43bb5710a",
              "conversation_name": "",
              "custom_attrs_bool": {},
              "custom_attrs_float": {},
              "custom_attrs_int": {},
              "custom_attrs_string": {},
              "ended_at": "2026-06-15T20:48:59.824899",
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
              "span_id": "0c4a245ea5896c6a",
              "span_kind": "CLIENT",
              "span_name": "invoke_agent",
              "started_at": "2026-06-15T20:48:59.823000",
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
              "trace_id": "fedd4b82b416b427c9ba4d06265870b7",
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
              "conversation_id": "019ecd06-f202-719b-867a-a6109d28ab44",
              "conversation_name": "",
              "custom_attrs_bool": {},
              "custom_attrs_float": {},
              "custom_attrs_int": {},
              "custom_attrs_string": {},
              "ended_at": "2026-06-15T20:44:04.994521",
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
              "span_id": "64e6a6908154d816",
              "span_kind": "CLIENT",
              "span_name": "invoke_agent",
              "started_at": "2026-06-15T20:44:04.994000",
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
              "trace_id": "4174234928825dd165b8f2180bd33a8d",
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

  describe('getAgentTraceChat', () => {
    vcrTest('gets the chat view for a trace', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentTraceChat({
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
      const resp = await client.getAgentTraceChat({
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

      const resp = await client.getAgentTraceChat({
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
        client.getAgentTraceChat({
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

  describe('getAgentConversationChat', () => {
    vcrTest('gets the chat view for a conversation', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.getAgentConversationChat({
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
      const resp = await client.getAgentConversationChat({
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

      const first = await client.getAgentConversationChat({
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

      const second = await client.getAgentConversationChat({
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

      const resp = await client.getAgentConversationChat({
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
        client.getAgentConversationChat({
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

  describe('searchAgentConversations', () => {
    vcrTest('searches agent conversations matching a query', async () => {
      await authenticate();
      const client = await init('example');
      const resp = await client.searchAgentConversations({
        query: 'Liverpool',
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
            {
              "agent_name": "",
              "conversation_id": "trace_a6fe0c92ca474ed0bd068c531f7af12c",
              "conversation_name": "",
              "last_activity": "2026-06-16T22:10:16.373000",
              "matched_messages": [
                {
                  "content_digest": "da504931273624ca2625eddf0089b5a4",
                  "content_preview": "[{"type": "text", "content": "Liverpool: Clear, 20\\u00b0C  \\nSan Francisco: Foggy, 18\\u00b0C"}]",
                  "role": "assistant",
                  "span_id": "46b56d77a8411c2d",
                  "started_at": "2026-06-16T22:10:16.373000",
                  "trace_id": "67648280e1e0dffe7e560df171d99ddc",
                },
                {
                  "content_digest": "f284331b6c45990fa0f3eee18d32dcb6",
                  "content_preview": "[{"type": "tool_call", "toolName": "get_weather", "arguments": "{\\"city\\":\\"Liverpool\\",\\"unit\\":\\"celsius\\"}"}, {"type": "tool_call", "toolName": "get_weather", "arguments": "{\\"city\\":\\"San Francisco\\",\\"unit\\":\\"celsius\\"}"}]",
                  "role": "assistant",
                  "span_id": "46b56d77a8411c2d",
                  "started_at": "2026-06-16T22:10:16.373000",
                  "trace_id": "67648280e1e0dffe7e560df171d99ddc",
                },
                {
                  "content_digest": "24b3dbc9126b55b3f896198f125ba7b8",
                  "content_preview": "[{"type": "text", "content": "What is the weather like in Liverpool and San Francisco?"}]",
                  "role": "user",
                  "span_id": "46b56d77a8411c2d",
                  "started_at": "2026-06-16T22:10:16.373000",
                  "trace_id": "67648280e1e0dffe7e560df171d99ddc",
                },
                {
                  "content_digest": "da504931273624ca2625eddf0089b5a4",
                  "content_preview": "[{"type": "text", "content": "Liverpool: Clear, 20\\u00b0C  \\nSan Francisco: Foggy, 18\\u00b0C"}]",
                  "role": "assistant",
                  "span_id": "00a5ca1e03e154e5",
                  "started_at": "2026-06-16T22:10:15.298000",
                  "trace_id": "67648280e1e0dffe7e560df171d99ddc",
                },
                {
                  "content_digest": "f284331b6c45990fa0f3eee18d32dcb6",
                  "content_preview": "[{"type": "tool_call", "toolName": "get_weather", "arguments": "{\\"city\\":\\"Liverpool\\",\\"unit\\":\\"celsius\\"}"}, {"type": "tool_call", "toolName": "get_weather", "arguments": "{\\"city\\":\\"San Francisco\\",\\"unit\\":\\"celsius\\"}"}]",
                  "role": "assistant",
                  "span_id": "00a5ca1e03e154e5",
                  "started_at": "2026-06-16T22:10:15.298000",
                  "trace_id": "67648280e1e0dffe7e560df171d99ddc",
                },
                {
                  "content_digest": "24b3dbc9126b55b3f896198f125ba7b8",
                  "content_preview": "[{"type": "text", "content": "What is the weather like in Liverpool and San Francisco?"}]",
                  "role": "user",
                  "span_id": "00a5ca1e03e154e5",
                  "started_at": "2026-06-16T22:10:15.298000",
                  "trace_id": "67648280e1e0dffe7e560df171d99ddc",
                },
              ],
            },
            {
              "agent_name": "",
              "conversation_id": "trace_a6bb4573d88e432487fd686bcea07fdd",
              "conversation_name": "",
              "last_activity": "2026-06-16T22:10:13.921000",
              "matched_messages": [
                {
                  "content_digest": "da504931273624ca2625eddf0089b5a4",
                  "content_preview": "[{"type": "text", "content": "Liverpool: Clear, 20\\u00b0C  \\nSan Francisco: Foggy, 18\\u00b0C"}]",
                  "role": "assistant",
                  "span_id": "b1204f4125fa14a3",
                  "started_at": "2026-06-16T22:10:13.921000",
                  "trace_id": "9f4808bfd047f16e362618f2efe5f813",
                },
                {
                  "content_digest": "f284331b6c45990fa0f3eee18d32dcb6",
                  "content_preview": "[{"type": "tool_call", "toolName": "get_weather", "arguments": "{\\"city\\":\\"Liverpool\\",\\"unit\\":\\"celsius\\"}"}, {"type": "tool_call", "toolName": "get_weather", "arguments": "{\\"city\\":\\"San Francisco\\",\\"unit\\":\\"celsius\\"}"}]",
                  "role": "assistant",
                  "span_id": "b1204f4125fa14a3",
                  "started_at": "2026-06-16T22:10:13.921000",
                  "trace_id": "9f4808bfd047f16e362618f2efe5f813",
                },
                {
                  "content_digest": "24b3dbc9126b55b3f896198f125ba7b8",
                  "content_preview": "[{"type": "text", "content": "What is the weather like in Liverpool and San Francisco?"}]",
                  "role": "user",
                  "span_id": "b1204f4125fa14a3",
                  "started_at": "2026-06-16T22:10:13.921000",
                  "trace_id": "9f4808bfd047f16e362618f2efe5f813",
                },
                {
                  "content_digest": "f9b958f7699f0fb3376ef72833b3a537",
                  "content_preview": "Liverpool: Clear, 20°C",
                  "role": "tool_result",
                  "span_id": "4cc40d210fb97a8f",
                  "started_at": "2026-06-16T22:10:13.918000",
                  "trace_id": "9f4808bfd047f16e362618f2efe5f813",
                },
                {
                  "content_digest": "824ba0a05444bfeed43610d6e6d7e4ec",
                  "content_preview": "{"city": "Liverpool", "unit": "celsius"}",
                  "role": "tool_call",
                  "span_id": "4cc40d210fb97a8f",
                  "started_at": "2026-06-16T22:10:13.918000",
                  "trace_id": "9f4808bfd047f16e362618f2efe5f813",
                },
                {
                  "content_digest": "5046fc9aeb351fb8fdef9a24d687e36c",
                  "content_preview": "[{"type": "tool_call", "toolCallId": "call_ejpNlstlWsztFSMBNzjSUJHy", "toolName": "get_weather", "arguments": "{\\"city\\":\\"Liverpool\\",\\"unit\\":\\"celsius\\"}"}, {"type": "tool_call", "toolCallId": "call_SPuh3HQgVJzEYXffdkE0TTdQ", "toolName": "get_weather", "arguments": "{\\"city\\":\\"San Francisco\\",\\"unit\\":\\"celsius\\"}"}]",
                  "role": "assistant",
                  "span_id": "38bad9c2d8bb3a1f",
                  "started_at": "2026-06-16T22:10:12.529000",
                  "trace_id": "9f4808bfd047f16e362618f2efe5f813",
                },
                {
                  "content_digest": "24b3dbc9126b55b3f896198f125ba7b8",
                  "content_preview": "[{"type": "text", "content": "What is the weather like in Liverpool and San Francisco?"}]",
                  "role": "user",
                  "span_id": "38bad9c2d8bb3a1f",
                  "started_at": "2026-06-16T22:10:12.529000",
                  "trace_id": "9f4808bfd047f16e362618f2efe5f813",
                },
              ],
            },
          ],
          "total_conversations": 3,
        }
      `);
    });

    vcrTest('supports limit and offset', async () => {
      await authenticate();
      const client = await init('example');

      const first = await client.searchAgentConversations({
        query: 'Liverpool',
        limit: 1,
      });
      expect(first.data).toMatchInlineSnapshot(`
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
              ],
            },
          ],
          "total_conversations": 1,
        }
      `);

      const second = await client.searchAgentConversations({
        query: 'Liverpool',
        limit: 1,
        offset: 1,
      });
      expect(second.data).toMatchInlineSnapshot(`
        {
          "results": [
            {
              "agent_name": "",
              "conversation_id": "trace_c50312356de3487fa90e381c9399b5b4",
              "conversation_name": "",
              "last_activity": "2026-06-16T22:10:34.631000",
              "matched_messages": [
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

      const resp = await client.searchAgentConversations({
        query: 'Liverpool',
        filters: {agent_name: 'my-cool-agent'},
      });
      expect(resp.data).toMatchInlineSnapshot(`
        {
          "results": [],
          "total_conversations": 0,
        }
      `);
    });

    vcrTest('filters by role', async () => {
      await authenticate();
      const client = await init('example');

      const resp = await client.searchAgentConversations({
        query: 'Liverpool',
        filters: {roles: ['user']},
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
              ],
            },
            {
              "agent_name": "",
              "conversation_id": "trace_a6fe0c92ca474ed0bd068c531f7af12c",
              "conversation_name": "",
              "last_activity": "2026-06-16T22:10:16.373000",
              "matched_messages": [
                {
                  "content_digest": "24b3dbc9126b55b3f896198f125ba7b8",
                  "content_preview": "[{"type": "text", "content": "What is the weather like in Liverpool and San Francisco?"}]",
                  "role": "user",
                  "span_id": "46b56d77a8411c2d",
                  "started_at": "2026-06-16T22:10:16.373000",
                  "trace_id": "67648280e1e0dffe7e560df171d99ddc",
                },
                {
                  "content_digest": "24b3dbc9126b55b3f896198f125ba7b8",
                  "content_preview": "[{"type": "text", "content": "What is the weather like in Liverpool and San Francisco?"}]",
                  "role": "user",
                  "span_id": "00a5ca1e03e154e5",
                  "started_at": "2026-06-16T22:10:15.298000",
                  "trace_id": "67648280e1e0dffe7e560df171d99ddc",
                },
              ],
            },
            {
              "agent_name": "",
              "conversation_id": "trace_a6bb4573d88e432487fd686bcea07fdd",
              "conversation_name": "",
              "last_activity": "2026-06-16T22:10:13.921000",
              "matched_messages": [
                {
                  "content_digest": "24b3dbc9126b55b3f896198f125ba7b8",
                  "content_preview": "[{"type": "text", "content": "What is the weather like in Liverpool and San Francisco?"}]",
                  "role": "user",
                  "span_id": "b1204f4125fa14a3",
                  "started_at": "2026-06-16T22:10:13.921000",
                  "trace_id": "9f4808bfd047f16e362618f2efe5f813",
                },
                {
                  "content_digest": "24b3dbc9126b55b3f896198f125ba7b8",
                  "content_preview": "[{"type": "text", "content": "What is the weather like in Liverpool and San Francisco?"}]",
                  "role": "user",
                  "span_id": "38bad9c2d8bb3a1f",
                  "started_at": "2026-06-16T22:10:12.529000",
                  "trace_id": "9f4808bfd047f16e362618f2efe5f813",
                },
              ],
            },
          ],
          "total_conversations": 3,
        }
      `);
    });

    vcrTest('returns no results for an unmatched query', async () => {
      await authenticate();
      const client = await init('example');

      const resp = await client.searchAgentConversations({
        query: 'asdkfjhasdkjfhakjsdhfkjasdh',
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

      expect(
        client.searchAgentConversations({query: 'Liverpool'})
      ).rejects.toMatchObject({
        data: null,
        error: {
          detail: 'Project not found',
        },
      });
    });
  });
});

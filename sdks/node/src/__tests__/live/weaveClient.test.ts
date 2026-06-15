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
});

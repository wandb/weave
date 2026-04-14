import {ContentType} from '../generated/traceServerApi';
import type {Api as TraceServerApi} from '../generated/traceServerApi';
import {
  LINK_TO_REGISTRY_PATH,
  createAndLinkWeaveAsset,
} from '../traceServerBindings/createAndLinkWeaveAsset';
import type {CreateAndLinkWeaveAssetReq} from '../traceServerBindings/createAndLinkWeaveAsset';

describe('createAndLinkWeaveAsset', () => {
  let mockTraceServerApi: jest.Mocked<TraceServerApi<unknown>>;

  beforeEach(() => {
    mockTraceServerApi = {
      request: jest.fn(),
    } as any;
  });

  it('posts the expected payload to /link_to_registry', async () => {
    const req: CreateAndLinkWeaveAssetReq = {
      ref: 'weave:///source-entity/source-project/object/my-prompt:v1',
      target: {
        entity_name: 'my-org',
        project_name: 'wandb-registry-prompts',
        portfolio_name: 'my-prompt-collection',
      },
      aliases: ['latest'],
    };

    mockTraceServerApi.request.mockResolvedValue({
      data: {version_index: 7},
    } as any);

    const result = await createAndLinkWeaveAsset(mockTraceServerApi, req);

    expect(result).toEqual({version_index: 7});
    expect(mockTraceServerApi.request).toHaveBeenCalledWith({
      path: LINK_TO_REGISTRY_PATH,
      method: 'POST',
      body: req,
      secure: true,
      type: ContentType.Json,
      format: 'json',
    });
  });

  it('preserves an empty aliases array', async () => {
    const req: CreateAndLinkWeaveAssetReq = {
      ref: 'weave:///source-entity/source-project/object/my-prompt:v1',
      target: {
        entity_name: 'my-org',
        project_name: 'wandb-registry-prompts',
        portfolio_name: 'my-prompt-collection',
      },
      aliases: [],
    };

    mockTraceServerApi.request.mockResolvedValue({
      data: {version_index: null},
    } as any);

    await createAndLinkWeaveAsset(mockTraceServerApi, req);

    expect(mockTraceServerApi.request).toHaveBeenCalledWith(
      expect.objectContaining({
        body: expect.objectContaining({
          aliases: [],
        }),
      })
    );
  });

  it('throws when the trace server returns invalid JSON', async () => {
    const req: CreateAndLinkWeaveAssetReq = {
      ref: 'weave:///source-entity/source-project/object/my-prompt:v1',
      target: {
        entity_name: 'my-org',
        project_name: 'wandb-registry-prompts',
        portfolio_name: 'my-prompt-collection',
      },
      aliases: [],
    };

    mockTraceServerApi.request.mockResolvedValue({
      data: null,
    } as any);

    await expect(
      createAndLinkWeaveAsset(mockTraceServerApi, req)
    ).rejects.toThrow('Trace server returned invalid JSON');
  });

  it('surfaces non-2xx request errors', async () => {
    const req: CreateAndLinkWeaveAssetReq = {
      ref: 'weave:///source-entity/source-project/object/my-prompt:v1',
      target: {
        entity_name: 'my-org',
        project_name: 'wandb-registry-prompts',
        portfolio_name: 'my-prompt-collection',
      },
      aliases: [],
    };
    const error = new Error('Request failed');

    mockTraceServerApi.request.mockRejectedValue(error);

    await expect(
      createAndLinkWeaveAsset(mockTraceServerApi, req)
    ).rejects.toThrow('Request failed');
  });
});

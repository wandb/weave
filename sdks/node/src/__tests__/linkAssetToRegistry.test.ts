import {ContentType} from '../generated/traceServerApi';
import type {Api as TraceServerApi} from '../generated/traceServerApi';
import {
  LINK_TO_REGISTRY_PATH,
  linkAssetToRegistry,
} from '../traceServerBindings/linkAssetToRegistry';
import type {LinkAssetToRegistryReq} from '../traceServerBindings/linkAssetToRegistry';

function makeReq(
  overrides: Partial<LinkAssetToRegistryReq> = {}
): LinkAssetToRegistryReq {
  return {
    ref: 'weave:///source-entity/source-project/object/my-prompt:v1',
    target: {
      entity_name: 'my-org',
      project_name: 'wandb-registry-prompts',
      portfolio_name: 'my-prompt-collection',
    },
    aliases: [],
    ...overrides,
  };
}

describe('linkAssetToRegistry', () => {
  let mockTraceServerApi: jest.Mocked<TraceServerApi<unknown>>;

  beforeEach(() => {
    mockTraceServerApi = {
      request: jest.fn(),
    } as any;
  });

  it('posts the expected payload to /link_to_registry', async () => {
    const req = makeReq({aliases: ['latest']});

    mockTraceServerApi.request.mockResolvedValue({
      data: {version_index: 7},
    } as any);

    const result = await linkAssetToRegistry(mockTraceServerApi, req);

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

  it('throws when the trace server returns invalid JSON', async () => {
    mockTraceServerApi.request.mockResolvedValue({
      data: null,
    } as any);

    await expect(
      linkAssetToRegistry(mockTraceServerApi, makeReq())
    ).rejects.toThrow('Trace server returned invalid JSON');
  });

  it('surfaces non-2xx request errors', async () => {
    const error = new Error('Request failed');
    mockTraceServerApi.request.mockRejectedValue(error);

    await expect(
      linkAssetToRegistry(mockTraceServerApi, makeReq())
    ).rejects.toThrow('Request failed');
  });
});

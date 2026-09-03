import type {WeaveTrace} from '../vendor/weave-server-sdk';
import {
  LINK_TO_REGISTRY_PATH,
  linkAssetToRegistry,
} from '../traceServerBindings/linkAssetToRegistry';
import type {LinkAssetToRegistryReq} from '../traceServerBindings/linkAssetToRegistry';
import {stainlessPromise, stainlessReject} from './helpers/stainlessPromise';

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
  let mockTraceServerApi: {post: jest.Mock};

  beforeEach(() => {
    mockTraceServerApi = {
      post: jest.fn(),
    };
  });

  it('posts the expected payload to /link_to_registry', async () => {
    const req = makeReq({aliases: ['latest']});

    mockTraceServerApi.post.mockReturnValue(
      stainlessPromise({version_index: 7})
    );

    const result = await linkAssetToRegistry(
      mockTraceServerApi as unknown as WeaveTrace,
      req
    );

    expect(result).toEqual({version_index: 7});
    expect(mockTraceServerApi.post).toHaveBeenCalledWith(
      LINK_TO_REGISTRY_PATH,
      {body: req}
    );
  });

  it('throws when the trace server returns invalid JSON', async () => {
    mockTraceServerApi.post.mockReturnValue(stainlessPromise(null));

    await expect(
      linkAssetToRegistry(
        mockTraceServerApi as unknown as WeaveTrace,
        makeReq()
      )
    ).rejects.toThrow('Trace server returned invalid JSON');
  });

  it('surfaces non-2xx request errors', async () => {
    const error = new Error('Request failed');
    mockTraceServerApi.post.mockReturnValue(stainlessReject(error));

    await expect(
      linkAssetToRegistry(
        mockTraceServerApi as unknown as WeaveTrace,
        makeReq()
      )
    ).rejects.toThrow('Request failed');
  });
});

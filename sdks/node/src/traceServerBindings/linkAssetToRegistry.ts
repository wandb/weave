import {asHttpResponse} from '../httpResponse';
import type {WeaveTrace} from '../vendor/weave-server-sdk';

export const LINK_TO_REGISTRY_PATH = '/link_to_registry';

export interface LinkAssetToRegistryTarget {
  entity_name: string;
  project_name: string;
  portfolio_name: string;
}

export interface LinkAssetToRegistryReq {
  ref: string;
  target: LinkAssetToRegistryTarget;
  aliases: string[];
}

export interface LinkAssetToRegistryRes {
  version_index: number | null;
}

/**
 * Link a published Weave asset version into a registry portfolio.
 *
 * @param traceServerApi - Initialized trace server API client.
 * @param req - Registry-link payload matching the `/link_to_registry` contract.
 * @returns Parsed response containing the linked portfolio version index.
 * @throws Error if the trace server returns invalid JSON.
 */
export async function linkAssetToRegistry(
  traceServerApi: WeaveTrace,
  req: LinkAssetToRegistryReq
): Promise<LinkAssetToRegistryRes> {
  const response = await asHttpResponse<LinkAssetToRegistryRes>(
    traceServerApi.post<LinkAssetToRegistryRes>(LINK_TO_REGISTRY_PATH, {
      body: req,
    })
  );

  if (response.data == null || typeof response.data !== 'object') {
    throw new Error('Trace server returned invalid JSON');
  }

  return response.data;
}

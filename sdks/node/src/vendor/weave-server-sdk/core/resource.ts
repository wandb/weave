// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import type { WeaveTrace } from '../client';

export abstract class APIResource {
  protected _client: WeaveTrace;

  constructor(client: WeaveTrace) {
    this._client = client;
  }
}

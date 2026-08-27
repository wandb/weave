// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import * as AgentsAPI from './agents';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';

export class Traces extends APIResource {
  /**
   * Genai Traces Chat
   */
  chat(body: TraceChatParams, options?: RequestOptions): APIPromise<AgentsAPI.AgentTraceChatRes> {
    return this._client.post('/agents/traces/chat', { body, ...options });
  }
}

export interface TraceChatParams {
  project_id: string;

  trace_id: string;

  include_feedback?: boolean;
}

export declare namespace Traces {
  export { type TraceChatParams as TraceChatParams };
}

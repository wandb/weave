// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';

export class Completions extends APIResource {
  /**
   * Completions Create
   */
  create(body: CompletionCreateParams, options?: RequestOptions): APIPromise<CompletionCreateResponse> {
    return this._client.post('/completions/create', { body, ...options });
  }
}

export interface CompletionCreateResponse {
  response: { [key: string]: unknown };

  conversation_id?: string | null;

  span_id?: string | null;

  trace_id?: string | null;

  weave_call_id?: string | null;
}

export interface CompletionCreateParams {
  inputs: CompletionCreateParams.Inputs;

  project_id: string;

  /**
   * Conversation ID to group related completions into a multi-turn conversation
   */
  conversation_id?: string | null;

  /**
   * Human-readable conversation name
   */
  conversation_name?: string | null;

  /**
   * Parent call ID to nest this LLM call under
   */
  parent_id?: string | null;

  /**
   * Source of the completion request (e.g. 'playground', 'signals')
   */
  source?: string | null;

  /**
   * Trace ID to use for the LLM call (for nesting under a parent)
   */
  trace_id?: string | null;

  /**
   * Whether to track this LLM call in the trace server
   */
  track_llm_call?: boolean | null;

  /**
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

export namespace CompletionCreateParams {
  export interface Inputs {
    model: string;

    api_version?: string | null;

    extra_headers?: { [key: string]: unknown } | null;

    frequency_penalty?: number | null;

    function_call?: string | null;

    functions?: Array<unknown> | null;

    logit_bias?: { [key: string]: unknown } | null;

    logprobs?: boolean | null;

    max_completion_tokens?: number | null;

    max_tokens?: number | null;

    messages?: Array<unknown>;

    modalities?: Array<unknown> | null;

    n?: number | null;

    parallel_tool_calls?: boolean | null;

    presence_penalty?: number | null;

    /**
     * Reference to a Weave Prompt object (e.g.,
     * 'weave:///entity/project/object/prompt_name:version'). If provided, the messages
     * from this prompt will be prepended to the messages in this request. Template
     * variables in the prompt messages can be substituted using the template_vars
     * parameter.
     */
    prompt?: string | null;

    reasoning_effort?: string | null;

    response_format?: { [key: string]: unknown } | unknown | null;

    seed?: number | null;

    stop?: string | Array<unknown> | null;

    stream?: boolean | null;

    temperature?: number | null;

    /**
     * Dictionary of template variables to substitute in prompt messages. Variables in
     * messages like '{variable_name}' will be replaced with the corresponding values.
     * Applied to both prompt messages (if prompt is provided) and regular messages.
     */
    template_vars?: { [key: string]: unknown } | null;

    timeout?: number | string | null;

    tool_choice?: string | { [key: string]: unknown } | null;

    tools?: Array<unknown> | null;

    top_logprobs?: number | null;

    top_p?: number | null;

    user?: string | null;

    /**
     * JSON string of Vertex AI service account credentials. When provided for
     * vertex_ai models (e.g. vertex_ai/gemini-2.5-pro), used for authentication
     * instead of api_key. Not persisted in trace storage.
     */
    vertex_credentials?: string | null;
  }
}

export declare namespace Completions {
  export {
    type CompletionCreateResponse as CompletionCreateResponse,
    type CompletionCreateParams as CompletionCreateParams,
  };
}

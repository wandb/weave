/**
 * Duck-typed interfaces for OpenAI Agents Realtime integration.
 *
 * These types mirror @openai/agents-realtime without importing from that
 * package, so the integration works without forcing it as a dependency.
 */

export interface RealtimeTransportLike {
  on(event: string, handler: (...args: any[]) => void): any;
  off(event: string, handler: (...args: any[]) => void): any;
  readonly status: string;
}

export interface RealtimeSessionLike {
  on(event: string, handler: (...args: any[]) => void): any;
  off(event: string, handler: (...args: any[]) => void): any;
  readonly transport: RealtimeTransportLike;
}

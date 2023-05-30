export type Tracer = <T>(label: string, doFn: (span?: Span) => T) => T;

export interface Span {
  addTags(keyValueMap: Record<string, any>): Span;
}

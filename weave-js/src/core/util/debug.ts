export function isWeaveDebugEnabled() {
  return typeof globalThis !== 'undefined' && (globalThis as any).WEAVE_DEBUG;
}

export function batchIntervalOverride() {
  return typeof globalThis !== 'undefined'
    ? (globalThis as any).WEAVE_BATCH_INTERVAL
    : undefined;
}

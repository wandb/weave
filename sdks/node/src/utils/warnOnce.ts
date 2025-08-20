const warnedKeys = new Set<string>();

export function warnOnce(key: string, message: string): void {
  if (!warnedKeys.has(key)) {
    console.warn(message);
    warnedKeys.add(key);
  }
}

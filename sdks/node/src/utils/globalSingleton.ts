/**
 * Returns a process-wide singleton keyed on `globalThis[Symbol.for(key)]`.
 *
 * This is the defence against the "dual-package hazard": if the same module
 * ends up loaded twice (e.g. once as CJS and once as ESM within the same
 * process, which can happen in mixed-module-system apps), each copy otherwise
 * owns its own module-scoped `let`/`const` state. Routing that state through
 * `globalThis` + a `Symbol.for` key makes the two copies resolve to the same
 * object, so state written by one is observable to the other.
 *
 * `Symbol.for(key)` is the realm-wide symbol registry — all calls with the
 * same string return the same symbol, across module copies.
 *
 * The `factory` is invoked only on first access; subsequent calls return the
 * already-stored value regardless of what `factory` would produce.
 */
export function globalSingleton<T>(key: string, factory: () => T): T {
  const sym = Symbol.for(key);
  const g = globalThis as {[sym: symbol]: T | undefined};
  return g[sym] ?? (g[sym] = factory());
}

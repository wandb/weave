const sym = Symbol.for('_weave_instrumentations');

(global as any)[sym] =
  (global as any)[sym] ||
  // key is the module name and sub path(lookup key),
  // value is an array of instrumentations pinned to an expected version range of the module
  new Map<string, Array<Pick<Instrumentation, 'version' | 'hook'>>>();

export default (global as any)[sym];

export type HookFn = (exports: any, name: string, baseDir: string) => any;

export interface Instrumentation {
  moduleName: string;
  subPath: string;
  version: string;
  hook: HookFn;
}

export function addInstrumentation({
  moduleName,
  subPath,
  version,
  hook,
}: Instrumentation) {
  const instrumentations = (global as any)[sym];

  const instrumentationLookupKey = `${moduleName}@${subPath}`;

  if (!instrumentations.has(instrumentationLookupKey)) {
    instrumentations.set(instrumentationLookupKey, []);
  }

  instrumentations.get(instrumentationLookupKey)!.push({
    version,
    hook,
  });
}

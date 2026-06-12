export type ColumnMapping<I, O> = {
  [K in keyof O]: keyof I;
};
export function mapArgs<
  T extends Record<string, any>,
  M extends Record<string, keyof T>,
>(input: T, mapping: M): {[K in keyof M]: T[M[K]]} {
  const result: Partial<{[K in keyof M]: T[M[K]]}> = {};

  for (const [newKey, oldKey] of Object.entries(mapping)) {
    if (oldKey in input) {
      result[newKey as keyof M] = input[oldKey];
    }
  }
  return result as {[K in keyof M]: T[M[K]]};
}

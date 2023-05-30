// Invert a Map<K,V> so it becomes Map<V,K>, while mapping K to NewV via keyToValue
export function invertRemap<OrigK, OrigV, NewV>(
  m: Map<OrigK, OrigV>,
  keyToValue: (key: OrigK, id: OrigV) => NewV
): Map<OrigV, NewV> {
  return new Map(Array.from(m, a => [a[1], keyToValue(a[0], a[1])]));
}

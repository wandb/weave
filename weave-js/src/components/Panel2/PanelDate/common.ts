export const inputType = {
  type: 'union' as const,
  members: ['date' as const, {type: 'timestamp' as const, unit: 'ms' as const}],
};

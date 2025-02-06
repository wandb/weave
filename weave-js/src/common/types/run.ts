export const LIST_RUNS_TYPE = {
  type: 'list' as const,
  objectType: {
    type: 'union' as const,
    members: ['none' as const, 'run' as const],
  },
};

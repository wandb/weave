export const inputType = {
  type: 'union' as const,
  members: [
    {
      type: 'dict' as const,
      objectType: {
        type: 'union' as const,
        members: ['none' as const, 'number' as const],
      },
    },
    {
      type: 'list' as const,
      maxLength: 25,
      objectType: {
        type: 'union' as const,
        members: ['none' as const, 'number' as const],
      },
    },
  ],
};

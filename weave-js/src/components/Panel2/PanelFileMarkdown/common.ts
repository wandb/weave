export const inputType = {
  type: 'union' as const,
  members: ['md', 'markdown'].map(extension => ({
    type: 'file' as const,
    extension,
  })),
};

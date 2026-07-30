export default {
  hooks: {
    onInsertPathParam: paramName =>
      paramName === 'runtimeName'
        ? `encodeURIComponent(${paramName})`
        : undefined,
  },
};

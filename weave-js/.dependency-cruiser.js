export default {
  forbidden: [
    {
      name: 'no-circular',
      severity: 'error',
      from: {
        pathNot: '^node_modules/.*',
      },
      to: {
        circular: true,
      },
    },
  ],
  options: {
    tsConfig: {
      fileName: './tsconfig.json',
    },
    doNotFollow: {
      path: 'node_modules|build|dist|logs',
    },
    cache: './node_modules/.cache/dependency-cruiser/app',
  },
};

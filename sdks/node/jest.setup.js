const path = require('path');

const liveTestTimeout = 20000; // 20 seconds

beforeEach(() => {
  const testPath = expect.getState().testPath;
  if (testPath && path.normalize(testPath).includes(path.normalize('/live/'))) {
    jest.setTimeout(liveTestTimeout);
  }
});

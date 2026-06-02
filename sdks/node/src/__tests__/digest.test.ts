import {computeDigest} from '../digest';

describe('computeDigest', () => {
  it('does something', () => {
    expect(computeDigest(Buffer.from('hello, world'))).toBe(
      'CcpXTqpuiunH0mEWcSkYSINkTQffunyYvEyKLgg2DVs'
    );
  });
});

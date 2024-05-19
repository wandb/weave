import {monthRoundedTime} from '@wandb/weave/common/util/time';

describe('Time tests', () => {
  it('convert seconds', () => {
    const timeStr = monthRoundedTime(100);
    expect(timeStr).toEqual('1m 40s');
  });
  it('convert small seconds', () => {
    const timeStr = monthRoundedTime(11);
    expect(timeStr).toEqual('11s');
  });
  it('convert large seconds', () => {
    const timeStr = monthRoundedTime(3019123);
    expect(timeStr).toEqual('1mo 4d 22h 38m 43s');
  });
  it('convert zero', () => {
    const timeStr = monthRoundedTime(0);
    expect(timeStr).toEqual('0s');
  });
});

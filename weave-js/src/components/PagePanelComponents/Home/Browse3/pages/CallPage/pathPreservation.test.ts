import {scorePathSimilarity, updatePath} from './pathPreservation';

describe('updatePath', () => {
  it('does not encode the root', () => {
    expect(updatePath('', 'root', -1)).toEqual('');
  });
  it('encodes the fourth call named child', () => {
    expect(updatePath('', 'child', 3)).toEqual('child*3'); // 0-indexed
  });
  it('encodes a grand child', () => {
    expect(updatePath('child*3', 'grandchild', 1)).toEqual(
      'child*3 grandchild*1'
    );
  });
});

describe('scorePathSimilarity', () => {
  it('returns 0 for identical paths', () => {
    expect(scorePathSimilarity('child*3', 'child*3')).toEqual(0);
  });
  it('returns infinity if no match', () => {
    expect(scorePathSimilarity('child*3', 'notchild*3')).toEqual(
      Number.POSITIVE_INFINITY
    );
  });
  it('returns difference in index for paths', () => {
    expect(scorePathSimilarity('child*3', 'child*5')).toEqual(2);
  });
  it('returns difference in index for deeper paths', () => {
    expect(
      scorePathSimilarity('child*3 grandchild*3', 'child*3 grandchild*5')
    ).toEqual(2);
  });
  it('supports paths of different lengths', () => {
    expect(scorePathSimilarity('child*3 grandchild*3', 'child*3')).toEqual(10);
  });
});

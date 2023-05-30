export type CompareOp = 'gte' | 'lte';

export function compare(op: CompareOp, x: number, y: number) {
  if (op === 'gte') {
    return x >= y;
  } else {
    return x <= y;
  }
}

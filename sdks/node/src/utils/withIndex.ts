// Once we update to ES2023:
// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/with
export function withIndex<T>(arr: T[], index: number, value: T): T[] {
  return [...arr].map((item, i) => (i === index ? value : item));
}

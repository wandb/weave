// Python reserved keywords
const RESERVED_KEYWORDS = new Set([
  'False',
  'None',
  'True',
  'and',
  'as',
  'assert',
  'async',
  'await',
  'break',
  'class',
  'continue',
  'def',
  'del',
  'elif',
  'else',
  'except',
  'finally',
  'for',
  'from',
  'global',
  'if',
  'import',
  'in',
  'is',
  'lambda',
  'nonlocal',
  'not',
  'or',
  'pass',
  'raise',
  'return',
  'try',
  'while',
  'with',
  'yield',
]);

export function isValidVarName(name: string): boolean {
  // Valid variable name according to python rules
  // Additionally, must be no longer than 255 characters
  return (
    name.length <= 255 &&
    !RESERVED_KEYWORDS.has(name) &&
    /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name)
  );
}

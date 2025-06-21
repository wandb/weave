export function transformNameToValid(value: string): string {
  return (
    value
      .trim()
      // Replace any character that's not a letter, number, hyphen, or underscore with a hyphen
      .replace(/[^a-zA-Z0-9\-_]/g, '-')
      // Replace multiple consecutive hyphens with a single hyphen
      .replace(/-+/g, '-')
      // Remove leading hyphens/underscores and ensure it starts with a letter or number
      .replace(/^[-_]+/, '')
      // Remove trailing hyphens/underscores
      .replace(/[-_]+$/, '')
      // If the result is empty or doesn't start with a letter/number, prepend 'name'
      .replace(/^$/, 'name')
      .replace(/^(?![a-zA-Z0-9])/, 'name-')
  );
}

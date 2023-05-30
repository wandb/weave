export function isInvalidTag(tag: string): boolean {
  // Function to validate string input for tags
  // Only allow users to input alphanumeric characters, underscores, hyphens, spaces
  // and colons. While this is already enforced on the backend, this function improves
  // the user experience for creating a new tag
  const reValidString = new RegExp('^[-:\\w\\s]*$');
  return !reValidString.test(tag);
}

declare module 'semifies' {
  /**
   * Checks if a version satisfies a version range
   * @param version - The version to check (e.g. "1.2.3")
   * @param range - The version range to check against (e.g. ">=1.2.0 <2.0.0")
   * @returns true if the version satisfies the range, false otherwise
   */
  function semifies(version: string, range: string): boolean;

  export default semifies;
}

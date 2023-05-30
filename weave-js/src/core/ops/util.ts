export const spread = <X>(arrayArgs: X[]): {[argName: string]: X} => {
  const result: {[argName: string]: X} = {};
  arrayArgs.forEach((v, i) => (result[i] = v));
  return result;
};

/**
 * Generates an array of length N with S uniformly distributed 1s and the rest 0s.
 *
 * @param N - The length of the resulting array.
 * @param S - The number of 1s to be uniformly distributed in the array.
 * @returns A number array of length N with S uniformly distributed 1s and the rest 0s.
 * @throws Will throw an error if S is greater than N.
 */
function generateArrayWithUniformOnes(N: number, S: number): boolean[] {
  if (S > N) {
    throw new Error('S must be less than or equal to N.');
  }

  // Create an array of length N filled with 0s
  const array: boolean[] = new Array(N).fill(false);

  // Distribute the 1s
  for (let i = 0; i < S; i++) {
    let index = Math.floor(Math.random() * N);

    // Ensure that the 1s are uniformly distributed by checking for duplicates
    while (array[index]) {
      index = Math.floor(Math.random() * N);
    }

    array[index] = true;
  }

  return array;
}

export function randomlyDownsample<T>(array: T[], n: number): T[] {
  // Check for invalid input
  if (n < 0 || !Number.isInteger(n)) {
    throw new Error('Invalid input: n must be a non-negative integer.');
  }

  // Return original array if n > array.length
  if (n >= array.length) {
    return array;
  }

  // Generate a boolean array with n 1s and the rest 0s
  const filter = generateArrayWithUniformOnes(array.length, n);

  // Filter the array
  return array.filter((_, i) => filter[i]);
}

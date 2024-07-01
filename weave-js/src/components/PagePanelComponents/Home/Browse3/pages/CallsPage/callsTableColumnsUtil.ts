/**
 * This implementation was created with assistance from ChatGPT, an AI developed by OpenAI.
 */

// Define types
export type Path = string[];
export type PathList = Path[];

export function stringToPath(str: string): Path {
  return str.split('.');
}

export function pathToString(path: Path): string {
  return path.join('.');
}

export function isDynamicCallColumn(path: Path): boolean {
  if (path.length === 1) {
    return path[0] === 'output';
  }
  return (
    path.length > 1 &&
    ['attributes', 'inputs', 'output', 'summary'].includes(path[0])
  );
}

// Helper function to check if two paths are equal
function pathsEqual(path1: Path, path2: Path): boolean {
  if (path1.length !== path2.length) {
    return false;
  }
  for (let i = 0; i < path1.length; i++) {
    if (path1[i] !== path2[i]) {
      return false;
    }
  }
  return true;
}

// Helper function to find the longest common prefix of two paths
function longestCommonPrefix(path1: Path, path2: Path): Path {
  const minLength = Math.min(path1.length, path2.length);
  const commonPrefix: Path = [];
  for (let i = 0; i < minLength; i++) {
    if (path1[i] === path2[i]) {
      commonPrefix.push(path1[i]);
    } else {
      break;
    }
  }
  return commonPrefix;
}

// Main function to insert a new path into the ordered list of paths
// Algorithm:
// Inputs:
// * L: an ordered list of unique paths
// * P: a new path to insert into the list
// Note: a "path" is a list of strings, indicating a hierarchy
// Returns:
// * N: an ordered list of unique paths
// Properties of N:
// * N is ordered and each path contained in N is unique (same as L)
// * N contains all elements of L
// * N also contains P
//    * If P is already in L, N is the same as L
//    * If P is not in L, N is L with P inserted at the appropriate position
// * The appropriate position is determined by the following rules:
//    * If P already exists in L, then do nothing
//    * Let C be the longest common prefix path between P and any element in L (allowing for empty prefix)
//        * If C == P, then insert P immediately before the first element in L that has a prefix of P
//        * Else, insert P immediately after the last element in L that has a prefix of C
export function insertPath(L: PathList, P: Path): PathList {
  // Check if P is already in L
  for (const path of L) {
    if (pathsEqual(path, P)) {
      return L;
    }
  }

  // Find the longest common prefix
  let maxPrefixLength = 0;
  let position = L.length; // Default position is at the end of the list

  for (let i = 0; i < L.length; i++) {
    const commonPrefix = longestCommonPrefix(L[i], P);
    if (commonPrefix.length > maxPrefixLength) {
      maxPrefixLength = commonPrefix.length;

      if (pathsEqual(commonPrefix, P)) {
        // Insert P immediately before the first element with a prefix of P
        position = i;
        break;
      } else {
        // Insert P immediately after the last element with a prefix of C
        position = i + 1;
      }
    } else if (commonPrefix.length === maxPrefixLength) {
      // If two paths have the same prefix length, insert P after the existing path
      position = i + 1;
    }
  }

  // Insert P into the determined position
  const N = [...L.slice(0, position), P, ...L.slice(position)];
  return N;
}

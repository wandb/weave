/**
 * Generates a consistent color for a given operation name.
 * Uses a simple but effective string hash that avoids bitwise operations.
 */
export const getColorForOpName = (opName: string): string => {
  // Use a simple string hash that sums char codes
  let hash = 0;
  for (let i = 0; i < opName.length; i++) {
    hash = Math.abs(hash * 31 + opName.charCodeAt(i));
  }

  // Use a more muted color palette
  // - Lower saturation (40% instead of 70%)
  // - Higher lightness (75% instead of 50%)
  // - Rotate hue to favor blue/purple/green spectrum
  const hue = (hash % 270) + 180; // Range from 180-450 (wraps around to 90), favoring cool colors
  return `hsl(${hue}, 40%, 75%)`;
};

/**
 * Formats a duration in milliseconds to a human-readable string
 */
export const formatDuration = (ms: number): string => {
  if (ms < 1000) {
    return `${ms.toFixed(0)}ms`;
  }
  return `${(ms / 1000).toFixed(2)}s`;
};

/**
 * Formats a timestamp to a human-readable string
 */
export const formatTimestamp = (timestamp: string): string => {
  return new Date(timestamp).toLocaleString();
};

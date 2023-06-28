export const hexToRGB = (hex: string, alpha?: number) => {
  if (!hex.startsWith('#')) {
    throw new Error(`Color hex code ${hex} missing '#' prefix`);
  }
  if (hex.length === 7) {
    const r = parseInt(hex.substring(1, 3), 16);
    const g = parseInt(hex.substring(3, 5), 16);
    const b = parseInt(hex.substring(5, 7), 16);
    if (isNaN(r) || isNaN(g) || isNaN(b)) {
      throw new Error(`Invalid hex code: ${hex}`);
    }
    return alpha !== undefined
      ? `rgba(${r}, ${g}, ${b}, ${alpha})`
      : `rgb(${r}, ${g}, ${b})`;
  }
  if (hex.length === 4) {
    const rc = parseInt(hex.charAt(1), 16);
    const gc = parseInt(hex.charAt(2), 16);
    const bc = parseInt(hex.charAt(3), 16);
    if (isNaN(rc) || isNaN(gc) || isNaN(bc)) {
      throw new Error(`Invalid hex code: ${hex}`);
    }
    const r = rc * 16 + rc;
    const g = gc * 16 + gc;
    const b = bc * 16 + bc;
    return alpha !== undefined
      ? `rgba(${r}, ${g}, ${b}, ${alpha})`
      : `rgb(${r}, ${g}, ${b})`;
  }
  throw new Error(`Invalid hex code: ${hex}`);
};

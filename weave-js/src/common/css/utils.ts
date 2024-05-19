const interpolate = (c1: number, c2: number, ratio: number) =>
  (1 - ratio) * c1 + ratio * c2;

const toHex = (value: number) => {
  const hex = Math.round(value).toString(16);
  return hex.length === 1 ? '0' + hex : hex;
};

export class Color {
  static fromHex(hex: string, alpha?: number): Color {
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
      return new Color(r, g, b, alpha);
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
      return new Color(r, g, b, alpha);
    }
    throw new Error(`Invalid hex code: ${hex}`);
  }

  r: number;
  g: number;
  b: number;
  a?: number;

  constructor(r: number, g: number, b: number, a?: number) {
    this.r = r;
    this.g = g;
    this.b = b;
    this.a = a;
  }

  alpha(): number {
    return this.a ?? 1.0;
  }

  withAlpha(a: number | undefined): Color {
    return new Color(this.r, this.g, this.b, a);
  }

  blend(other: Color): Color {
    const ratio = other.alpha();
    const r = Math.floor(interpolate(this.r, other.r, ratio));
    const g = Math.floor(interpolate(this.g, other.g, ratio));
    const b = Math.floor(interpolate(this.b, other.b, ratio));
    return new Color(r, g, b);
  }

  toHexString(): string {
    const hex = `#${toHex(this.r)}${toHex(this.g)}${toHex(this.b)}`;
    const suffix = this.a != null ? toHex(this.alpha() * 255) : '';
    return `${hex}${suffix}`;
  }

  toString(): string {
    if (this.a != null) {
      return `rgba(${this.r}, ${this.g}, ${this.b}, ${this.a})`;
    }
    return `rgb(${this.r}, ${this.g}, ${this.b})`;
  }
}

export const hexToRGB = (hex: string, alpha?: number) => {
  return Color.fromHex(hex, alpha).toString();
};

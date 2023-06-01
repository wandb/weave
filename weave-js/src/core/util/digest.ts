declare global {
  interface String {
    padStart(length: number, char: string): string;
  }
}

declare function atob(s: string): string;
declare function btoa(s: string): string;

// To make this module isomorphic
const localAtoB =
  typeof atob !== 'undefined'
    ? atob
    : (b64: string): string => Buffer.from(b64, 'base64').toString('binary');
const localBToA =
  typeof btoa !== 'undefined'
    ? btoa
    : (binary: string): string => Buffer.from(binary).toString('base64');

export function b64ToHex(b64String: string) {
  try {
    const dig = localAtoB(b64String);
    let result = '';
    for (const c of dig) {
      result += c.charCodeAt(0).toString(16).padStart(2, '0');
    }
    return result;
  } catch (e) {
    console.error('Unable to decode digest: ', b64String);
    return b64String;
  }
}

export function hexToId(hex: string) {
  try {
    let result = '';
    for (let i = 0; i < hex.length; i += 2) {
      result += String.fromCharCode(parseInt(hex.substr(i, 2), 16));
    }
    return localBToA(result);
  } catch (e) {
    console.error('Unable to decode digest: ', hex);
    return hex;
  }
}

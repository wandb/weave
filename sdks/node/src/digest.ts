import {Buffer} from 'buffer';
import crypto from 'crypto';

export function computeDigest(data: Buffer): string {
  // Must match python server algorithm in clickhouse_trace_server_batched.py
  const hasher = crypto.createHash('sha256');
  hasher.update(data);
  const hashBytes = hasher.digest();
  const base64EncodedHash = hashBytes.toString('base64url');
  return base64EncodedHash
    .replace(/-/g, 'X')
    .replace(/_/g, 'Y')
    .replace(/=/g, '');
}

export function stringDigest(data: string): string {
  return computeDigest(Buffer.from(data));
}

export function encodeNumber(num: number): string {
  return String(num);
}

export function stringifyPythonDumps(obj: any): string {
  if (obj === null) {
    return 'null';
  }
  if (typeof obj === 'string') {
    return JSON.stringify(obj);
  }
  if (typeof obj === 'number' || typeof obj === 'boolean') {
    return String(obj);
  }
  if (Array.isArray(obj)) {
    const items = obj.map(stringifyPythonDumps);
    return '[' + items.join(', ') + ']';
  }
  if (typeof obj === 'object') {
    const pairs = Object.keys(obj)
      .sort()
      .map(key => JSON.stringify(key) + ': ' + stringifyPythonDumps(obj[key]));
    return '{' + pairs.join(', ') + '}';
  }
  throw new Error('Unsupported type');
}

export function valDigest(data: any): string {
  return stringDigest(stringifyPythonDumps(data));
}

import type {Buffer} from 'buffer';
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

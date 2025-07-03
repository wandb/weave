// src/memoizedParser.ts

import { TraceCallSchema, SCHEMA_PARSERS } from './schemas';

/**
 * An efficient, non-exported recursive function that searches for the
 * presence of a document. It stops and returns `true` on the first match.
 *
 * @param node The data structure to search within.
 * @returns `true` if a parsable document is found, otherwise `false`.
 */
function hasDocuments(node: unknown): boolean {
  // 1. Check if the node itself can be parsed by any of our schemas.
  for (const parser of SCHEMA_PARSERS) {
    if (parser.schema.safeParse(node).success) {
      return true; // Success! A document was found.
    }
  }

  // 2. If not, recurse into arrays or objects.
  if (Array.isArray(node)) {
    // .some() is efficient because it stops iterating on the first `true` result.
    return node.some(item => hasDocuments(item));
  } else if (node && typeof node === 'object') {
    // Recurse into object values, returning immediately if a document is found.
    for (const key in node) {
      if (Object.prototype.hasOwnProperty.call(node, key)) {
        if (hasDocuments((node as Record<string, unknown>)[key])) {
          return true;
        }
      }
    }
  }

  // 3. If the entire structure has been searched with no matches.
  return false;
}

// The cache will store results for the lifetime of the application session.
const documentDetectionCache = new Map<string, boolean>();

/**
 * Checks if a TraceCall contains any data that can be parsed into a Document.
 * This function is memoized based on the trace ID to provide fast, stable
 * results suitable for use in React components and hooks.
 *
 * @param trace The raw TraceCall object.
 * @returns `true` if any documents are found, `false` otherwise.
 */
export function callHasDocuments(trace: TraceCallSchema): boolean {
  // Check the cache first for an instant result.
  if (documentDetectionCache.has(trace.id)) {
    return documentDetectionCache.get(trace.id)!;
  }

  // If not cached, perform the efficient detection logic.
  const result = hasDocuments(trace.inputs) || hasDocuments(trace.output);

  // Store the new result in the cache before returning.
  documentDetectionCache.set(trace.id, result);

  return result;
}

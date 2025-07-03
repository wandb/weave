// src/parser.ts (Updated)

import {
  SCHEMA_PARSERS,
  TraceCallSchema,
  WeaveDocumentSchema,
  ParseResult,
  ParsedCall,
} from './schemas';

// --- Caches ---
const parsedCallCache = new Map<string, ParsedCall<WeaveDocumentSchema, 'Document'>>();

// --- Private Implementation Functions ---
function findAllDocuments(
  node: unknown
): ParseResult<WeaveDocumentSchema, 'Document'>[] {
  const allFound: ParseResult<WeaveDocumentSchema, 'Document'>[] = [];

  for (const parser of SCHEMA_PARSERS) {
    const parseResult = parser.schema.safeParse(node);
    if (parseResult.success) {
      allFound.push({
        schema: 'Document',
        result: parseResult.data,
      });
      return allFound;
    }
  }

  if (Array.isArray(node)) {
    for (const item of node) {
      allFound.push(...findAllDocuments(item));
    }
  } else if (node && typeof node === 'object') {
    for (const key in node) {
      if (Object.prototype.hasOwnProperty.call(node, key)) {
        allFound.push(...findAllDocuments((node as Record<string, unknown>)[key]));
      }
    }
  }

  return allFound;
}

/**
 * Aggregates arrays of documents and returns null if the final list is empty.
 */
function aggregateAndFinalize<T>(results: T[][]): T[] | null {
  const flattened = results.flat();
  return flattened.length > 0 ? flattened : null;
}


/**
 * The core, non-memoized parsing logic, updated for the new schema.
 */
function _getTraceDocuments(
  trace: TraceCallSchema
): ParsedCall<WeaveDocumentSchema, 'Document'> { // Return type is updated
  // Find all ParseResult objects in the output (if present)
  const outputResults = 'output' in trace ? findAllDocuments(trace.output) : [];

  // Find all ParseResult objects in the inputs
  const inputParseResults = findAllDocuments(trace.inputs);
 
  // Extract the document arrays (WeaveDocumentSchema[][]) from the input results
  const inputDocumentArrays = inputParseResults.map(pr => pr.result);

  return {
    id: trace.id,
    // Aggregate all found input documents into a single array, or null
    inputs: aggregateAndFinalize(inputDocumentArrays),
    // If the list of output results is empty, return null
    output: outputResults.length > 0 ? outputResults : null,
  };
}


// --- Public, Memoized API ---

/**
 * The public API remains the same, but its return type has been updated
 * automatically via TypeScript inference.
 */
export function getTraceDocuments(
  trace: TraceCallSchema
): ParsedCall<WeaveDocumentSchema, 'Document'> {
  if (parsedCallCache.has(trace.id)) {
    return parsedCallCache.get(trace.id)!;
  }
  const result = _getTraceDocuments(trace);
  parsedCallCache.set(trace.id, result);
  return result;
}

export function callHasDocuments(
  trace: TraceCallSchema
): boolean {
  const { inputs, output } = getTraceDocuments(trace);
  return inputs !== null || output !== null
}

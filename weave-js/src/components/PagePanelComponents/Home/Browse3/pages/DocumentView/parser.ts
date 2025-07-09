import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {
  ParsedCall,
  ParseResult,
  SCHEMA_PARSERS,
  TraceCallSchema,
  WeaveDocumentSchema,
} from './schemas';

// Cached call parses
const parsedCallCache = new Map<string, ParsedCall<WeaveDocumentSchema>>();

function findAllDocuments(node: unknown): ParseResult<WeaveDocumentSchema>[] {
  const allFound: ParseResult<WeaveDocumentSchema>[] = [];

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
        allFound.push(
          ...findAllDocuments((node as Record<string, unknown>)[key])
        );
      }
    }
  }

  return allFound;
}

/**
 * The core, non-memoized parsing logic, updated for the new schema.
 */
function _getTraceDocuments(
  trace: TraceCallSchema
): ParsedCall<WeaveDocumentSchema> {
  // Return type is updated
  // Find all ParseResult objects in the output (if present)
  const parsedOutputs = 'output' in trace ? findAllDocuments(trace.output) : [];

  // Find all ParseResult objects in the inputs
  const parsedInputs = findAllDocuments(trace.inputs);

  return {
    id: trace.id,
    // Aggregate all found input documents into a single array, or null
    inputs: parsedInputs,
    // If the list of output results is empty, return null
    output: parsedOutputs,
  };
}

// --- Public, Memoized API ---

/**
 * The public API remains the same, but its return type has been updated
 * automatically via TypeScript inference.
 */
export function getTraceDocuments(
  trace: TraceCallSchema
): ParsedCall<WeaveDocumentSchema> {
  if (parsedCallCache.has(trace.id)) {
    return parsedCallCache.get(trace.id)!;
  }
  const result = _getTraceDocuments(trace);
  parsedCallCache.set(trace.id, result);
  return result;
}

export function parseCall(call: CallSchema): ParsedCall<WeaveDocumentSchema> {
  if (!call.traceCall) {
    return getTraceDocuments({
      id: call.traceId,
      inputs: {},
    });
  }
  return getTraceDocuments(call.traceCall);
}

export function callHasDocuments(trace: TraceCallSchema): boolean {

  const isValid = (val: null | any[]) => {
    return val !== null && val.length > 0;
  }

  const {inputs, output} = getTraceDocuments(trace);
  return isValid(inputs) || isValid(output);
}

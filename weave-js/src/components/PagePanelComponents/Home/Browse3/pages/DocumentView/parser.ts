import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {
  ParsedCall,
  ParseResult,
  SCHEMA_PARSERS,
  TraceCallMinimalSchema,
  WeaveDocument,
} from './schemas';

function findAllDocuments(node: unknown): ParseResult<WeaveDocument>[] {
  const allFound: ParseResult<WeaveDocument>[] = [];

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

// The core, parsing logic
function getTraceDocuments(
  trace: TraceCallMinimalSchema
): ParsedCall<WeaveDocument> {
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

export function parseCall(call: CallSchema): ParsedCall<WeaveDocument> {
  if (!call.traceCall) {
    return getTraceDocuments({
      id: call.traceId,
      inputs: {},
    });
  }
  return getTraceDocuments(call.traceCall);
}

export function callHasDocuments(trace: TraceCallMinimalSchema): boolean {
  const isValid = (val: null | any[]) => {
    return val !== null && val.length > 0;
  };

  const {inputs, output} = getTraceDocuments(trace);
  return isValid(inputs) || isValid(output);
}

import {CallStackEntry} from './weaveClient';

/**
 * Represents a summary object with string keys and any type of values.
 */
type Summary = Record<string, any>;
/**
 * Merges two summary objects, combining their values.
 *
 * @param left - The first summary object to merge.
 * @param right - The second summary object to merge.
 * @returns A new summary object containing the merged values.
 *
 * This function performs a deep merge of two summary objects:
 * - For numeric values, it adds them together.
 * - For nested objects, it recursively merges them.
 * - For other types, the left value "wins".
 */
function mergeSummaries(left: Summary, right: Summary): Summary {
  const result: Summary = {...right};
  for (const [key, leftValue] of Object.entries(left)) {
    if (key in result) {
      if (typeof leftValue === 'number' && typeof result[key] === 'number') {
        result[key] = leftValue + result[key];
      } else if (
        typeof leftValue === 'object' &&
        typeof result[key] === 'object'
      ) {
        result[key] = mergeSummaries(leftValue, result[key]);
      } else {
        result[key] = leftValue;
      }
    } else {
      result[key] = leftValue;
    }
  }
  return result;
}

export function processSummary(
  result: any,
  summarize: ((result: any) => Record<string, any>) | undefined,
  currentCall: CallStackEntry,
  parentCall: CallStackEntry | undefined
) {
  let ownSummary = summarize ? summarize(result) : {};

  if (ownSummary.usage) {
    for (const model in ownSummary.usage) {
      if (typeof ownSummary.usage[model] === 'object') {
        ownSummary.usage[model] = {
          requests: 1,
          ...ownSummary.usage[model],
        };
      }
    }
  }

  const mergedSummary = mergeSummaries(ownSummary, currentCall.childSummary);

  if (parentCall) {
    parentCall.childSummary = mergeSummaries(
      mergedSummary,
      parentCall.childSummary
    );
  }

  return mergedSummary;
}

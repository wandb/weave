import {RUNNABLE_FEEDBACK_TYPE_PREFIX} from '../StructuredFeedback/runnableFeedbackTypes';

export const RUNNABLE_FEEDBACK_IN_SUMMARY_PREFIX =
  'summary.weave.feedback.' + RUNNABLE_FEEDBACK_TYPE_PREFIX;
export const RUNNABLE_FEEDBACK_OUTPUT_PART = 'payload.output';

export type ScorerFeedbackTypeParts = {
  scorerName: string;
  scorePath: string;
};

export const parseScorerFeedbackField = (
  inputField: string
): ScorerFeedbackTypeParts | null => {
  const prefix = RUNNABLE_FEEDBACK_IN_SUMMARY_PREFIX + '.';
  if (!inputField.startsWith(prefix)) {
    return null;
  }
  const res = inputField.replace(prefix, '');
  if (!res.includes('.')) {
    return null;
  }
  const [scorerName, ...rest] = res.split('.');
  const prefixedScorePath = rest.join('.');
  const pathPrefix = RUNNABLE_FEEDBACK_OUTPUT_PART;
  if (!prefixedScorePath.startsWith(pathPrefix)) {
    return null;
  }
  const scorePath = prefixedScorePath.replace(pathPrefix, '');
  return {
    scorerName,
    scorePath,
  };
};

export const convertScorerFeedbackFieldToBackendFilter = (
  field: string
): string => {
  const parsed = parseScorerFeedbackField(field);
  if (parsed === null) {
    return field;
  }
  const {scorerName, scorePath} = parsed;
  return `feedback.[${RUNNABLE_FEEDBACK_TYPE_PREFIX}.${scorerName}].${RUNNABLE_FEEDBACK_OUTPUT_PART}${scorePath}`;
};

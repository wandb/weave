export type ScorerFeedbackTypeParts = {
  scorerName: string;
  scorePath: string;
};

export const parseScorerFeedbackType = (
  inputField: string
): ScorerFeedbackTypeParts | null => {
  const prefix = 'summary.weave.feedback.wandb.runnable.';
  if (!inputField.startsWith(prefix)) {
    return null;
  }
  const res = inputField.replace(prefix, '');
  if (!res.includes('.')) {
    return null;
  }
  const [scorerName, ...rest] = res.split('.');
  const prefixedScorePath = rest.join('.');
  const pathPrefix = 'payload.output.';
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
  const parsed = parseScorerFeedbackType(field);
  if (parsed === null) {
    return field;
  }
  const {scorerName, scorePath} = parsed;
  return `feedback.[wandb.runnable.${scorerName}].payload.output.${scorePath}`;
};

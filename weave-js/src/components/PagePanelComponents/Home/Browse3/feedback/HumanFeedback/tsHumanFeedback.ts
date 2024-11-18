export type FeedbackTypeParts = {
  fullType: string;
  userDefinedType: string;
  feedbackType: string;
};

export const parseFeedbackType = (field: string): FeedbackTypeParts | null => {
  // feedback.wandb.annotation.Numerical-field-2.payload.value
  // fullType: feedback.wandb.annotation.Numerical-field-2
  // userDefinedType: Numerical-field-2
  // type: annotation
  const deBracketed = field.replace(/\[.*\]/g, '');
  const split = deBracketed.split('.');
  if (split.length !== 6) {
    return null;
  }
  const [f, w, type, userDefinedType, p, v] = split;

  if (f !== 'feedback') {
    throw new Error(`Expected 'feedback' prefix, got '${f}'`);
  }
  if (v !== 'value') {
    throw new Error(`Expected 'value' prefix, got '${v}'`);
  }
  if (p !== 'payload') {
    throw new Error(`Expected 'payload' prefix, got '${p}'`);
  }
  if (w !== 'wandb') {
    return null;
  }
  return {
    fullType: [f, w, type, userDefinedType].join('.'),
    feedbackType: type,
    userDefinedType,
  };
};

export const convertFeedbackFieldToBackendFilter = (field: string): string => {
  const parsed = parseFeedbackType(field);
  if (parsed === null) {
    return field;
  }
  const {feedbackType, userDefinedType} = parsed;
  return `feedback.[wandb.${feedbackType}.${userDefinedType}].payload.value`;
};

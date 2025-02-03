export type FeedbackTypeParts = {
  field: string;
  userDefinedType: string;
  feedbackType: string;
  displayName: string;
};

export const parseFeedbackType = (
  inputField: string
): FeedbackTypeParts | null => {
  // input: summary.weave.feedback.wandb.annotation.Numerical-field-2.payload.value
  // or input: wandb.annotation.Numerical-field-2.payload.value
  // or input: feedback.[wandb.annotation.Numerical-field-2].payload.value
  //
  // output:
  // field: wandb.annotation.Numerical-field-2
  // userDefinedType: Numerical-field-2
  // type: annotation
  // displayName: Annotation.Numerical-field-2

  // If the field is coming from the flattened table, remove the
  // summary portion
  const field = inputField.startsWith('summary.weave.feedback')
    ? inputField.replace('summary.weave.feedback.', '')
    : inputField;
  const deBracketed = field.replace(/\[.*\]/g, '');
  const split = deBracketed.split('.');
  if (split.length !== 5) {
    return null;
  }
  const [w, type, userDefinedType, p, v] = split;

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
    field,
    feedbackType: type,
    userDefinedType,
    displayName: `${
      type.charAt(0).toUpperCase() + type.slice(1)
    }.${userDefinedType}`,
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

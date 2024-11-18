export type FeedbackTypeParts = {
  value: any;
  fullType: string;
  userDefinedType: string;
  feedbackType: string;
};

export const parseFeedbackType = (field: string): FeedbackTypeParts => {
  // feedback.wandb.annotation.Text-field-2.value.Text-field-2.ZQUEOy2FtgkRWahm8ucKgGHQGQYhoroXSug6SY6SSZQ
  // userDefinedType: Text-field-2
  // type: annotation
  // value: Text-field-2.ZQUEOy2FtgkRWahm8ucKgGHQGQYhoroXSug6SY6SSZQ
  const deBracketed = field.replace(/\[.*\]/g, '');
  const [f, w, type, userDefinedType, v, u2, hash] = deBracketed.split('.');

  if (f !== 'feedback') {
    throw new Error(`Expected 'feedback' prefix, got ${f}`);
  }
  if (v !== 'value') {
    throw new Error(`Expected 'value' prefix, got ${v}`);
  }
  if (w !== 'wandb') {
    // don't try to parse non-wandb feedback
    return {
      value: field,
      fullType: field,
      feedbackType: field,
      userDefinedType: field,
    };
  }
  if (userDefinedType !== u2) {
    throw new Error(
      `Malformed feedback field: userDefinedType ${userDefinedType} does not match payload type: ${u2} (${field})`
    );
  }
  const value = `${userDefinedType}.${hash}`;
  return {
    value,
    fullType: field,
    feedbackType: type,
    userDefinedType,
  };
};

export const convertFeedbackFieldToBackendFilter = (field: string): string => {
  const {feedbackType, userDefinedType, value} = parseFeedbackType(field);
  return `feedback.[wandb.${feedbackType}.${userDefinedType}].value.${value}`;
};

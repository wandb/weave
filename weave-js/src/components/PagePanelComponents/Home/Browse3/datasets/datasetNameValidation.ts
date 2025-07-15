export interface DatasetNameValidationResult {
  isValid: boolean;
  error: string | null;
}

export function validateDatasetName(
  value: string
): DatasetNameValidationResult {
  if (!value.trim()) {
    return {
      isValid: false,
      error: 'Dataset name cannot be empty',
    };
  }

  // Use simpler regex matching backend: check for any invalid characters
  const invalidRegex = /[^\w.-]/;
  if (invalidRegex.test(value)) {
    const invalidChars = [
      ...new Set(
        value
          .split('')
          .filter(c => invalidRegex.test(c))
          .map(c => (c === ' ' ? '&lt;space&gt;' : c))
      ),
    ].join(', ');
    return {
      isValid: false,
      error: `Invalid characters found: ${invalidChars}`,
    };
  }

  return {
    isValid: true,
    error: null,
  };
}

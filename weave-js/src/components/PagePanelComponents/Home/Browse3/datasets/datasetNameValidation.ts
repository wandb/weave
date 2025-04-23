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
      error: null,
    };
  }

  try {
    // First check if it starts with a letter or number
    if (!/^[a-zA-Z0-9]/.test(value)) {
      return {
        isValid: false,
        error: 'Dataset name must start with a letter or number',
      };
    }

    // Then check if it only contains allowed characters
    if (!/^[a-zA-Z0-9\-_]+$/.test(value)) {
      const invalidChars = [
        ...new Set(
          value
            .split('')
            .filter(c => !/[a-zA-Z0-9\-_]/.test(c))
            .map(c => (c === ' ' ? '<space>' : c))
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
  } catch (e) {
    return {
      isValid: false,
      error: e instanceof Error ? e.message : 'Invalid dataset name',
    };
  }
}

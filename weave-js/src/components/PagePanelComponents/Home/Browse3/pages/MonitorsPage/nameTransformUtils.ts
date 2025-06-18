export interface NameTransformResult {
  transformedName: string;
  hasChanged: boolean;
  message: string | null;
}

export function transformToValidName(input: string): NameTransformResult {
  const trimmedInput = input.trim();

  if (!trimmedInput) {
    return {
      transformedName: '',
      hasChanged: false,
      message: null,
    };
  }

  let transformed = trimmedInput;

  // Replace spaces with hyphens
  transformed = transformed.replace(/\s+/g, '-');

  // Replace any invalid characters with hyphens
  transformed = transformed.replace(/[^a-zA-Z0-9\-_]/g, '-');

  // Replace multiple consecutive hyphens with a single hyphen
  transformed = transformed.replace(/-+/g, '-');

  // Remove leading hyphens/underscores if they exist and the string doesn't start with a letter/number
  transformed = transformed.replace(/^[-_]+/, '');

  // Remove trailing hyphens/underscores
  transformed = transformed.replace(/[-_]+$/, '');

  // If the name still doesn't start with a letter or number after transformation, prepend 'monitor-'
  if (transformed && !/^[a-zA-Z0-9]/.test(transformed)) {
    transformed = 'monitor-' + transformed;
  }

  // If the entire string was invalid characters, provide a default
  if (!transformed) {
    transformed = 'monitor-' + Date.now();
  }

  const hasChanged = transformed !== trimmedInput;

  return {
    transformedName: transformed,
    hasChanged,
    message: hasChanged
      ? `Your name "${trimmedInput}" will be saved as "${transformed}".`
      : null,
  };
}

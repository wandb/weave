/**
 * Type guard for OpenAI-style chunks.
 */
export const isOpenAIChunk = (
  chunk: unknown
): chunk is {
  choices: Array<{
    delta: {
      content?: string;
    };
  }>;
} => {
  return (
    typeof chunk === 'object' &&
    chunk !== null &&
    'choices' in chunk &&
    Array.isArray((chunk as any).choices) &&
    (chunk as any).choices.length > 0 &&
    'delta' in (chunk as any).choices[0]
  );
};

/**
 * Type guard for simple content chunks.
 */
export const isContentChunk = (
  chunk: unknown
): chunk is {
  content: string;
} => {
  return (
    typeof chunk === 'object' &&
    chunk !== null &&
    'content' in chunk &&
    typeof (chunk as any).content === 'string'
  );
};

/**
 * Extract content from a chunk, handling different chunk formats.
 */
export const extractChunkContent = (chunk: unknown): string | null => {
  if (isOpenAIChunk(chunk)) {
    return chunk.choices[0]?.delta?.content || null;
  }

  if (isContentChunk(chunk)) {
    return chunk.content;
  }

  if (typeof chunk === 'string') {
    return chunk;
  }

  return null;
};

/**
 * Filter out undefined values from an object.
 */
export const filterUndefined = <T extends Record<string, any>>(
  obj: T
): Record<string, any> => {
  return Object.fromEntries(
    Object.entries(obj).filter(([_, value]) => value !== undefined)
  );
};

/**
 * Check if a value is a ResponseFormat object (has a 'type' property).
 */
export const isResponseFormat = (value: unknown): value is {type: string} => {
  return typeof value === 'object' && value !== null && 'type' in value;
};

/**
 * Type guard for OpenAI-style streaming chunks.
 *
 * @param chunk The chunk to check
 * @returns True if the chunk has OpenAI format with choices array containing delta objects
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
 * Type guard for simple content chunks with a direct 'content' property.
 *
 * @param chunk The chunk to check
 * @returns True if the chunk has a 'content' property with a string value
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
 *
 * Supports OpenAI-style chunks, simple content chunks, and plain strings.
 *
 * @param chunk The chunk to extract content from
 * @returns The extracted content string, or null if no content found
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
 *
 * Creates a new object containing only properties with defined values.
 *
 * @param obj The object to filter
 * @returns A new object with undefined values removed
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
 *
 * @param value The value to check
 * @returns True if the value is an object with a 'type' property
 */
export const isResponseFormat = (value: unknown): value is {type: string} => {
  return typeof value === 'object' && value !== null && 'type' in value;
};

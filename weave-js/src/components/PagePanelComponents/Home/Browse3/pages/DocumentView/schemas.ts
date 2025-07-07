// src/schemas.ts (Updated)

import { z } from 'zod';

// region: Provided Type Definitions (Unchanged)
export type ID = string | number;
export type Metadata = Record<string, any>;
export type Content = string;
// ... and other base types
export type KeyedDictType = {
  [key: string]: any;
  _keys?: string[];
};
export type TraceCallSchema = {
  id: string;
  inputs: KeyedDictType;
  output?: unknown;
};
// endregion


// region: Target Type Definitions (MODIFIED)

/**
 * The canonical schema for a single document. (Unchanged)
 */
export const WeaveDocumentSchema = z.object({
  id: z.union([z.string(), z.number()]).optional(),
  content: z.string(),
  metadata: z.record(z.any()).optional(),
  extra: z.record(z.any()).optional(),
});
export type WeaveDocumentSchema = z.infer<typeof WeaveDocumentSchema>;

/**
 * A wrapper for a successful parse. The result is now always an array.
 */
export type ParseResult<T, R extends string> = {
  schema: R;
  result: T[]; // MODIFIED: No longer OneOrMany<T>, always T[]
};

/**
 * The final output. Fields are now either an array or null.
 */
export type ParsedCall<T, R extends string> = {
  id: string;
  inputs: ParseResult<T, R>[] | null; // MODIFIED: No longer OneOrMany<T>
  output: ParseResult<T, R>[] | null; // MODIFIED: No longer OneOrMany<...>
};
// endregion


// region: Source Schema Parsers (MODIFIED)

// --- Parser 1: LangchainDocument ---
const LangchainDocumentSourceSchema = z.object({
    page_content: z.string(),
    metadata: z.record(z.any()).optional(),
}).catchall(z.any());

// MODIFIED: The transform now wraps the single document in an array.
const LangchainParser = LangchainDocumentSourceSchema.transform(
  (doc): WeaveDocumentSchema[] => { // Return type is now an array
    const { page_content, metadata, ...extra } = doc;
    const result: WeaveDocumentSchema = {
      content: page_content,
      metadata,
    };
    if (Object.keys(extra).length > 0) {
      result.extra = extra;
    }
    return [result]; // Always return an array
  }
);

// --- Parser 2: ChromaQueryResult ---
const ChromaQueryResultSourceSchema = z.object({
  ids: z.union([z.string(), z.number(), z.array(z.union([z.string(), z.number()]))]),
  documents: z.union([z.string(), z.array(z.string())]).optional(),
  metadatas: z.array(z.record(z.any())).optional(),
}).catchall(z.any());

// Unchanged: This parser already returns an array.
const ChromaParser = ChromaQueryResultSourceSchema.transform(
    (queryResult): WeaveDocumentSchema[] => {
        // ... implementation is the same, as it already returns WeaveDocumentSchema[]
        const ids = Array.isArray(queryResult.ids) ? queryResult.ids : [queryResult.ids];
        const documents = queryResult.documents ? (Array.isArray(queryResult.documents) ? queryResult.documents : [queryResult.documents]) : [];
        const metadatas = queryResult.metadatas ? (Array.isArray(queryResult.metadatas) ? queryResult.metadatas : [queryResult.metadatas]) : [];
        
        return ids.map((id, i) => ({
            id,
            content: documents[i] ?? '',
            metadata: metadatas?.[i],
        }));
    }
);

// The registry remains structurally the same.
export const SCHEMA_PARSERS: { name: string; schema: z.ZodTypeAny }[] = [
  { name: 'LangchainDocument', schema: LangchainParser },
  { name: 'ChromaQueryResult', schema: ChromaParser },
];
// endregion

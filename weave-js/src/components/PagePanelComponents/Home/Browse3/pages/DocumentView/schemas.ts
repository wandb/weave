// src/schemas.ts (Updated)

import {z} from 'zod';

// region: Provided Type Definitions (Unchanged)
export type ID = string | number;
export type Metadata = Record<string, any>;
export type Content = string;

export type KeyedDictType = {
  [key: string]: any;
  _keys?: string[];
};

export const WeaveDocumentSchema = z.object({
  id: z.union([z.string(), z.number()]).optional(),
  content: z.string(),
  metadata: z.record(z.any()).optional(),
  extra: z.record(z.any()).optional(),
});
export type WeaveDocumentSchemaType = z.infer<typeof WeaveDocumentSchema>;

export type ParseResult<T> = {
  schema: string;
  result: T[];
};

export type ParsedCall<T> = {
  id: string;
  inputs: ParseResult<T>[] | null;
  output: ParseResult<T>[] | null;
};

const LangchainDocumentSourceSchema = z
  .object({
    page_content: z.string(),
    metadata: z.record(z.any()).optional(),
  })
  .catchall(z.any());

const LangchainParser = LangchainDocumentSourceSchema.transform(
  (doc): WeaveDocumentSchemaType[] => {
    const {page_content, metadata, ...extra} = doc;
    const result: WeaveDocumentSchemaType = {
      content: page_content,
      metadata,
    };
    if (Object.keys(extra).length > 0) {
      result.extra = extra;
    }
    return [result]; // Always return an array
  }
);

const ChromaQueryResultSourceSchema = z
  .object({
    ids: z.union([
      z.string(),
      z.number(),
      z.array(z.union([z.string(), z.number()])),
    ]),
    documents: z.union([z.string(), z.array(z.string())]).optional(),
    metadatas: z.array(z.record(z.any())).optional(),
  })
  .catchall(z.any());

const ChromaParser = ChromaQueryResultSourceSchema.transform(
  (queryResult): WeaveDocumentSchemaType[] => {
    const ids = Array.isArray(queryResult.ids)
      ? queryResult.ids
      : [queryResult.ids];
    const documents = queryResult.documents
      ? Array.isArray(queryResult.documents)
        ? queryResult.documents
        : [queryResult.documents]
      : [];
    const metadatas = queryResult.metadatas
      ? Array.isArray(queryResult.metadatas)
        ? queryResult.metadatas
        : [queryResult.metadatas]
      : [];

    return ids.map((id, i) => ({
      id,
      content: documents[i] ?? '',
      metadata: metadatas?.[i],
    }));
  }
);

export const SCHEMA_PARSERS: {name: string; schema: z.ZodTypeAny}[] = [
  {name: 'LangchainDocument', schema: LangchainParser},
  {name: 'ChromaQueryResult', schema: ChromaParser},
];

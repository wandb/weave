import {z} from 'zod';

export type ID = string | number;
export type Metadata = Record<string, any>;
export type Content = string;

export type TraceCallMinimalSchema = {
  id: string;
  inputs: KeyedDictType;
  output?: unknown;
};

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

export type WeaveDocument = z.infer<typeof WeaveDocumentSchema>;

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
  (doc): WeaveDocument[] => {
    const {page_content, metadata, ...extra} = doc;
    const result: WeaveDocument = {
      content: page_content,
      metadata,
    };
    if (Object.keys(extra).length > 0) {
      result.extra = extra;
    }
    return [result]; // Always return an array
  }
);

const IDSchema = z.union([z.string(), z.number()]);
const MetadataSchema = z.record(z.any());

// This schema accepts both GetResult (flat arrays) and QueryResult (nested arrays).
const ChromaGetOrQueryResultSourceSchema = z
  .object({
    ids: z.union([z.array(IDSchema), z.array(z.array(IDSchema))]),
    documents: z
      .union([z.array(z.string()), z.array(z.array(z.string()))])
      .optional()
      .nullable(),
    metadatas: z
      .union([z.array(MetadataSchema), z.array(z.array(MetadataSchema))])
      .optional()
      .nullable(),
  })
  .catchall(z.any());

// This unified parser handles both GetResult and QueryResult.
const ChromaParser = ChromaGetOrQueryResultSourceSchema.transform(
  (queryResult): WeaveDocument[] => {
    const ids: ID[] = queryResult.ids.flat();
    const documents: Content[] = queryResult.documents?.flat() ?? [];
    const metadatas: Metadata[] = queryResult.metadatas?.flat() ?? [];

    // Map the normalized, flat arrays to the target WeaveDocument structure.
    return ids.map((id, i) => ({
      id,
      content: documents[i] ?? '',
      metadata: metadatas?.[i],
    }));
  }
);

// Export the available parsers
export const SCHEMA_PARSERS: {name: string; schema: z.ZodTypeAny}[] = [
  {name: 'LangchainDocument', schema: LangchainParser},
  {name: 'ChromaResult', schema: ChromaParser},
];

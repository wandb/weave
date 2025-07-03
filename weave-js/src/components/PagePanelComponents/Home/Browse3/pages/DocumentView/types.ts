import {KeyedDictType, TraceCallSchema} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/traceServerClientTypes'

export type OneOrMany<T> = T | [T];
export type ID = string | number;
export type Embedding = number | string;
export type Metadata = Record<string, any>;
export type URI = string;

export interface ChromaQueryResultSchema {
  ids: OneOrMany<ID>,
  embeddings?: OneOrMany<Embedding>,
  metadatas?: OneOrMany<Metadata>,
  documents?: OneOrMany<String>,
  images?: OneOrMany<any>, // This should probably be parsed to either PIL or Content
  uris?: OneOrMany<URI>,
}

export interface ChromaDocumentSchema {
  id: ID,
  embedding?: Embedding,
  metadata?: Metadata,
  document?: String,
  image?: any, // This should probably be parsed to either PIL or Content internally
  uri?: URI,
}

export interface LangchainDocumentSchema {
  id?: string | number
  page_contents: string
  metadata?: Record<any, any>
  type: "Document"
}

interface LangchainDocument {
  id?: string | number
  page_contents: string
  metadata?: Record<any, any>
  type: "Document"
}
export interface WeaveDocument {
  id?: string
  metadata?: KeyedDictType
  content: string
  extra: KeyedDictType
}

export const SUPPORTED_FILE_EXTENSIONS = [
  'csv',
  'tsv',
  'json',
  'jsonl',
] as const;
export type SupportedFileExtension = (typeof SUPPORTED_FILE_EXTENSIONS)[number];

export const FILE_FORMAT_MIME_TYPES = {
  csv: 'text/csv',
  tsv: 'text/tab-separated-values',
  json: 'application/json',
  jsonl: 'application/x-jsonlines',
} as const;

export const FILE_FORMAT_DELIMITERS = {
  csv: ',',
  tsv: '\t',
} as const;

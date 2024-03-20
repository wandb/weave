export const PROJECT_CALL_STREAM_NAME = 'stream';
export const WANDB_ARTIFACT_REF_SCHEME = 'wandb-artifact';
export const WANDB_ARTIFACT_REF_PREFIX = `${WANDB_ARTIFACT_REF_SCHEME}:///`;
export const WEAVE_REF_SCHEME = 'weave';
export const WEAVE_REF_PREFIX = `${WEAVE_REF_SCHEME}:///`;
export const WILDCARD_ARTIFACT_VERSION_AND_PATH = ':*/obj';
export const DICT_KEY_EDGE_TYPE = 'key';
export const LIST_INDEX_EDGE_TYPE = 'ndx';
export const TABLE_ID_EDGE_TYPE = 'id';
export const OBJECT_ATTRIBUTE_EDGE_TYPE = 'atr';
export const TABLE_ROW_EDGE_TYPE = 'row';
export const TABLE_COLUMN_EDGE_TYPE = 'col';
export const OP_CATEGORIES = [
  'train',
  'predict',
  'score',
  'evaluate',
  'tune',
] as const;
export const OBJECT_CATEGORIES = ['model', 'dataset'] as const;

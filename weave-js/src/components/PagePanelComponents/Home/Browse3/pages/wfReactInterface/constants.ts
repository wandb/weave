export const PROJECT_CALL_STREAM_NAME = 'stream';
export const WANDB_ARTIFACT_REF_SCHEME = 'wandb-artifact';
export const WANDB_ARTIFACT_REF_PREFIX = `${WANDB_ARTIFACT_REF_SCHEME}:///`;
export const WEAVE_REF_SCHEME = 'weave';
export const WEAVE_REF_PREFIX = `${WEAVE_REF_SCHEME}:///`;
export const WEAVE_PRIVATE_SCHEME = 'weave-private';
export const WEAVE_PRIVATE_PREFIX = `${WEAVE_PRIVATE_SCHEME}:///`;
export const WILDCARD_ARTIFACT_VERSION_AND_PATH = ':*/obj';
export const DICT_KEY_EDGE_NAME = 'key';
export const LIST_INDEX_EDGE_NAME = 'index';
export const TABLE_ID_EDGE_NAME = 'id';
export const OBJECT_ATTR_EDGE_NAME = 'attr';
export const AWL_ROW_EDGE_NAME = 'row';
export const AWL_COL_EDGE_NAME = 'col';
export const OP_CATEGORIES = [
  'train',
  'predict',
  'score',
  'evaluate',
  'tune',
] as const;
export const KNOWN_BASE_OBJECT_CLASSES = ['Model', 'Dataset'] as const;

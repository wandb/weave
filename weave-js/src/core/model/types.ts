import {compact} from 'lodash';

/** *******************/
/* Weave Type System */
/** *******************/

export const ALL_BASIC_TYPES = [
  'invalid',
  'any',
  'unknown',
  'string',
  'id',
  'number',
  'boolean',
  'date',
  'report',
  'artifact',
  'artifactMembership',
  'artifactVersion',
  'artifactType',
  'artifactAlias',
  'run',
  'entity',
  'project',
  'org',
  'user',
  'type', // #!
  'link',
  'none',
  'runQueue',
  // Weave Python additions
  'histogram',
  'int',
  'float',
  'sqlconnection',
  // End Weave Python additions
] as const;

export type BasicType = (typeof ALL_BASIC_TYPES)[number];

export type SimpleType = BasicType;

// Weave Python additions
export interface ConstType<T extends Type = Type> {
  type: 'const';
  valType: T;
  val: any;
}

export interface PanelType {
  type: 'Panel';
}

export interface ContainerPanelType {
  type: 'container_panel_type';
}

type PanelSubType = ContainerPanelType;

export const PanelSubTypes: ContainerPanelType[] = [
  {type: 'container_panel_type'},
];

interface ObjectTypeAttrs {
  [key: string]: Type;
}
interface ObjectTypeBase {
  type: string;
  _is_object: true;
  _base_type: Type;
}
export type ObjectType = ObjectTypeBase & ObjectTypeAttrs;

// End Weave Python additions

// TODO: figure out how this merges with dict
export interface TypedDictType {
  type: 'typedDict';

  // undefined here forces us to handle cases where properties
  // missing
  propertyTypes: {[key: string]: Type | undefined};

  notRequiredKeys?: string[];
}

export interface RootObjectType {
  type: 'Object';
}

export interface Dict<T extends Type = Type> {
  type: 'dict';
  objectType: T;
}

export interface TaggedValueType<T extends Type = Type, V extends Type = Type> {
  type: 'tagged';
  tag: T;
  value: V;
}

export interface ListType<T extends Type = Type> {
  type: 'list';
  objectType: T;
  // length?: number;
  minLength?: number;
  maxLength?: number;
}

// Hardcoded list of types which are W&B specific (likely would not be
// included in an open source version)
export const WANDB_DOMAIN_TYPES = [
  'report',
  'artifact',
  'artifactVersion',
  'artifactType',
  'run',
  'entity',
  'project',
  'org',
  'user',
  'image-file',
  'video-file',
  'audio-file',
  'html-file',
  'bokeh-file',
  'object3D-file',
  'molecule-file',
  'table',
  'joined-table',
  'partitioned-table',
  'file',
  'dir',
  'runQueue',
  'wb_trace_tree',
  'histogram',
] as const;

export const BASIC_MEDIA_TYPES: MediaType[] = [
  {type: 'image-file'},
  {type: 'video-file'},
  {type: 'audio-file'},
  {type: 'html-file'},
  {type: 'bokeh-file'},
  {type: 'object3D-file'},
  {type: 'molecule-file'},
  {type: 'pytorch-model-file'},
  {type: 'table', columnTypes: {}},
  {type: 'joined-table', columnTypes: {}},
  {type: 'partitioned-table', columnTypes: {}},
  {type: 'wb_trace_tree'},
];
// TODO: make this systematic -- we should use some kind of registry
// to ensure that every type is included
export const TYPES_WITH_PAGES: Type[] = [
  ...ALL_BASIC_TYPES.filter(
    t => !['none', 'invalid', 'any', 'unknown'].includes(t)
  ),

  ...BASIC_MEDIA_TYPES,

  ...compact(
    WANDB_DOMAIN_TYPES.map(typeId => {
      if (BASIC_MEDIA_TYPES.find(t => t.type === typeId)) {
        // this was already covered by BasicMediaTypes above
        return null;
      }

      return {type: typeId} as Type;
    })
  ),

  {
    type: 'ndarray',
    serializationPath: {
      key: '',
      path: '',
    },
    shape: [],
  },

  {
    type: 'timestamp',
    unit: 'ms',
  } as const,
];

export const SORTABLE_TYPES: Type[] = [
  'id',
  'string',
  'number',
  'boolean',
  'none',
  {type: 'timestamp', unit: 'ms'},
];

export const TYPES_WITH_DIGEST: Type[] = [
  {type: 'image-file'},
  {type: 'video-file'},
  {type: 'audio-file'},
  {type: 'object3D-file'},
  {type: 'molecule-file'},
  {type: 'pytorch-model-file'},
];

export const GROUPABLE_TYPES: Type[] = SORTABLE_TYPES.concat(
  SORTABLE_TYPES.map(t => ({
    type: 'dict',
    objectType: {type: 'union', members: ['none', t]},
  })),
  SORTABLE_TYPES.map(t => ({
    type: 'list',
    maxLength: 10,
    objectType: {type: 'union', members: ['none', t]},
  }))
).concat(TYPES_WITH_DIGEST);

export const ALL_LIST_TYPES = [
  'list' as const,
  'ArrowWeaveList' as const,
  'dataframeTable' as const,
  'groupresult' as const,
  'runs' as const,
];

export interface AllListType<T extends Type = Type> {
  type: (typeof ALL_LIST_TYPES)[number];
  objectType: T;
  minLength?: number;
  maxLength?: number;
}

// Used to denote support for any dimension of object.
// 0d: obj
// 1d: Array<obj>
// 2d: Array<Array<obj>>
// ...
// Note this is currently not used anywhere, but I'm keeping
// it because I like the idea (tensor is nested arrays)
// export interface Tensor {
//   type: 'tensor';
//   objectType: Type;
// }

export interface ImageType {
  type: 'image-file';
  boxLayers?: {[layerName: string]: string[]};
  boxScoreKeys?: string[];
  maskLayers?: {[layerName: string]: string[]};
  classMap?: {[key: string]: string};
}

export interface VideoType {
  type: 'video-file';
}

export interface AudioType {
  type: 'audio-file';
}

export interface HtmlType {
  type: 'html-file';
}

export interface BokehType {
  type: 'bokeh-file';
}

export interface Object3DType {
  type: 'object3D-file';
}

export interface MoleculeType {
  type: 'molecule-file';
}

export interface PytorchSavedModelType {
  type: 'pytorch-model-file';
}

export interface TableType {
  type: 'table';
  columnTypes: {[key: string]: Type};
}

export interface JoinedTableType {
  type: 'joined-table';
  columnTypes: {[key: string]: Type};
}

export interface PartitionedTableType {
  type: 'partitioned-table';
  columnTypes: {[key: string]: Type};
}

export interface WBTraceTreeType {
  type: 'wb_trace_tree';
}

export type MediaType =
  | ImageType
  | VideoType
  | AudioType
  | HtmlType
  | BokehType
  | Object3DType
  | MoleculeType
  | PytorchSavedModelType
  | TableType
  | JoinedTableType
  | PartitionedTableType
  | WBTraceTreeType;

export type MediaTypesWithoutPath = WBTraceTreeType;

export interface FunctionInputTypes {
  [key: string]: Type;
}

export interface FunctionType {
  type: 'function';
  inputTypes: FunctionInputTypes;
  outputType: Type;
}

export interface FunctionTypeSpecific<
  InputTypes extends FunctionInputTypes = FunctionInputTypes,
  ReturnType extends Type = 'any'
> {
  type: 'function';
  inputTypes: InputTypes;
  outputType: ReturnType;
}

export interface File {
  type: 'file';
  extension?: string;
  wbObjectType?: MediaType | 'none';
}

export interface Dir {
  type: 'dir';
}

/// // Weave Python additions
// localdir should be a subtype of dir and assignable anywhere dir is
// assignable. But the type system doesn't support sub-typing yet.
export interface LocalDir {
  type: 'localdir';
}

export type AllDirType = Dir | LocalDir;
export interface NewImage {
  type: 'pil_image';
  // width: number;
  // height: number;
  // mode: string;
}

export interface Histogram {
  bins: number[];
  values: number[];
}

/// // End Weave Python additions

export interface Union {
  type: 'union';
  members: Type[];
}

export interface NDArrayType {
  type: 'ndarray';
  serializationPath: {
    key: string;
    path: string;
  };
  shape: number[];
}

export interface TimestampType {
  type: 'timestamp';
  // TODO: support additional units in the future.
  unit?: 'ms';
}

export type QueryPath = ObjectId;

export interface Link {
  name: string;
  url: string;
}

// Weave Python additions
export interface SizedStringConfig {
  type: 'sizedstringconfig';
}
export interface Gpt3FineTuneType {
  type: 'gpt3_fine_tune_type';
}

export interface HistogramType {
  type: 'histogram';
}

export interface NewRunType {
  type: 'run-type';
  _output: Type;
}

export interface NewRun {
  _state: {_val: string};
  _prints: string[];
}

export interface OpDefType {
  type: 'OpDef';
}

export interface RefType {
  type: 'Ref';
}

export interface WandbArtifactRef {
  type: 'WandbArtifactRef';
}

export interface FilesystemArtifact {
  type: 'FilesystemArtifact';
}

export interface FilesystemArtifactRef {
  type: 'FilesystemArtifactRef';
}

export interface StreamTable {
  type: 'stream_table';
}

// End Weave Python additions

export type ComplexType =
  // Weave Python additions
  | ConstType
  | SizedStringConfig
  | Gpt3FineTuneType
  | NewRunType
  | PanelType
  | PanelSubType
  | NewImage
  | FilesystemArtifact
  | FilesystemArtifactRef
  | StreamTable
  // End Weave Python additions
  | HistogramType
  | TypedDictType
  | RootObjectType
  | AllListType // WeavePython: changed this to support many list types
  // | Tensor
  | Dict
  | TaggedValueType
  | TableType
  | JoinedTableType
  | PartitionedTableType
  | MediaType
  | MediaTypesWithoutPath
  | AllDirType
  | File
  | FunctionType
  | Union
  | NDArrayType
  | TimestampType
  | OpDefType
  | RefType
  | WandbArtifactRef;
export type Type = ComplexType | SimpleType;

export type TypeID = ComplexType['type'] | SimpleType;

// Files related stuff
export interface ObjectId {
  entityName: string;
  projectName: string;
  artifactTypeName: string;
  artifactSequenceName: string;
  artifactCommitHash: string;
}
export interface ReadyManifest {
  manifest: Manifest;
  layout: 'V1' | 'V2';
  rootMetadata: DirMetadata;
}

export interface FileEntry {
  size: number;
  ref?: string;
  digest?: string;
  birthArtifactID?: string;
}

export interface Manifest {
  storagePolicy: string;
  storagePolicyConfig: {[key: string]: any};
  contents: {[name: string]: FileEntry};
}

export type FullFilePath = ObjectId & {
  path: string;
};

export interface FileDesc {
  fullPath: FullFilePath | null;
  loading: boolean;
  contents: string | null;
}

export interface FileDirectUrl {
  fullPath: FullFilePath;
  refPath: ObjectId | null;
  loading: boolean;
  directUrl: string | null;
}
export interface DirMetadata {
  type: 'dir';
  fullPath: string;
  size: number;

  dirs: {[name: string]: DirMetadata};
  files: {[name: string]: FileMetadata};
}

export type FileMetadata = {
  type: 'file';
  fullPath: string;
  url: string;
} & FileEntry;
export type MetadataNode = DirMetadata | FileMetadata;

export interface FilePathWithMetadata {
  path: FullFilePath;
  metadata: MetadataNode | null;
}

export interface PathMetadata {
  fullPath: FullFilePath;
  loading: boolean;
  node: MetadataNode | null;
}

export interface FilePathMetadata {
  fullPath: FullFilePath;
  loading: boolean;
  node: FileMetadata;
}

export interface LoadedPathMetadata {
  _type: 'loaded-path';
  fullPath: FullFilePath;
  node: MetadataNode | null;
}

export interface ArtifactFileId {
  artifactId: string;
  path: string;
}

export interface ArtifactFileContent {
  refFileId: ArtifactFileId | null;
  contents: string | null;
}

export interface ArtifactFileDirectUrl {
  refFileId: ArtifactFileId | null;
  directUrl: string | null;
}

export interface RunPathInfo {
  entityName: string;
  projectName: string;
  runId: string;
}

export type RunFileIdWithPathInfo = RunFileId & RunPathInfo;

export interface RunFileId {
  runId: string;
  path: string;
}

export interface RunFileContent {
  contents: string | null;
}

export interface RunFileDirectUrl {
  directUrl: string | null;
}

export interface PathType {
  path: string[];
  type: Type;
}

export interface ConcreteTaggedValue<Tag = any, Value = any> {
  _tag: Tag;
  _value: Value;
}
export type Val<Value, Tag = unknown> = Value | ConcreteTaggedValue<Tag, Value>;

export const ALL_DIR_TYPE = {
  type: 'union' as const,
  members: [{type: 'dir' as const}, {type: 'localdir' as const}],
};

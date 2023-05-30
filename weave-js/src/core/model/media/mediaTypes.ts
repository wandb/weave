export type WBType = {
  wb_type: string;
  params?: {[key: string]: any};
};

export type ConstWBType<T = any> = WBType & {
  wb_type: 'const';
  params: {
    is_set?: boolean;
    val: T;
  };
};

export const isConstWBType = (t: WBType): t is ConstWBType => {
  return t.wb_type === 'const';
};

export type PythonObjectWBType = WBType & {
  // 'object' kept for legacy reasons
  wb_type: 'pythonObject' | 'object';
  params: {
    class_name: string;
  };
};

export const isPythonObjectWBType = (t: WBType): t is PythonObjectWBType => {
  return t.wb_type === 'pythonObject' || t.wb_type === 'object';
};

export type TypedDictWBType = WBType & {
  // dictionary kept for legacy reasons
  wb_type: 'dictionary' | 'typedDict';
  params: {
    type_map: {[columnName: string]: WBType};
  };
};

export const isTypedDictWBType = (t: WBType): t is TypedDictWBType => {
  return t.wb_type === 'dictionary' || t.wb_type === 'typedDict';
};

export type ListWBType = WBType & {
  wb_type: 'list';
  params: {
    element_type: WBType;
    length?: number;
  };
};

export const isListWBType = (t: WBType): t is ListWBType => {
  return t.wb_type === 'list';
};

export type UnionWBType = WBType & {
  wb_type: 'union';
  params: {
    allowed_types: WBType[];
  };
};

export const isUnionWBType = (t: WBType): t is UnionWBType => {
  return t.wb_type === 'union';
};

export type ForeignKeyWBType = WBType & {
  // 'wandb.TableForeignKey' kept for legacy reasons
  wb_type: 'wandb.TableForeignKey' | 'foreignKey';
  params: {
    element_type: WBType;
    length?: number;
  };
};

export const isForeignKeyWBType = (t: WBType): t is ForeignKeyWBType => {
  return t.wb_type === 'wandb.TableForeignKey' || t.wb_type === 'foreignKey';
};

export type ForeignIndexWBType = WBType & {
  // 'wandb.TableForeignIndex' kept for legacy reasons
  wb_type: 'wandb.TableForeignIndex' | 'foreignIndex';
  params: {
    element_type: WBType;
    length?: number;
  };
};

export const isForeignIndexWBType = (t: WBType): t is ForeignIndexWBType => {
  return (
    t.wb_type === 'wandb.TableForeignIndex' || t.wb_type === 'foreignIndex'
  );
};

export type PrimaryKeyWBType = WBType & {
  // 'wandb.TablePrimaryKey' kept for legacy reasons
  wb_type: 'wandb.TablePrimaryKey' | 'primaryKey';
  params: {
    element_type: WBType;
    length?: number;
  };
};

export const isPrimaryKeyWBType = (t: WBType): t is PrimaryKeyWBType => {
  return t.wb_type === 'wandb.TablePrimaryKey' || t.wb_type === 'primaryKey';
};

export type NDArrayWBType = WBType & {
  wb_type: 'ndarray';
  params: {
    serialization_path: {
      path: string;
      key: string;
    };
    shape: number[];
  };
};

export const isNDArrayWBType = (t: WBType): t is NDArrayWBType => {
  return t.wb_type === 'ndarray';
};

export type ClassesIdWBType = WBType & {
  // 'wandb.Classes_id' kept for legacy reasons
  wb_type: 'wandb.Classes_id' | 'classesId';
};

export const isClassesIdWBType = (t: WBType): t is ClassesIdWBType => {
  return t.wb_type === 'wandb.Classes_id' || t.wb_type === 'ClassesId';
};

export type TableWBType = WBType & {
  // 'wandb.Table' kept for legacy reasons
  wb_type: 'wandb.Table' | 'table';
};

export const isTableWBType = (t: WBType): t is TableWBType => {
  return t.wb_type === 'wandb.Table' || t.wb_type === 'table';
};

export type ImageFileWBType = WBType & {
  // 'wandb.Image' kept for legacy reasons
  wb_type: 'wandb.Image' | 'image-file';
  // TODO: add params if we ever want to pull param data
  params?: {
    box_layers?: ConstWBType<{[layerName: string]: string[]}>;
    mask_layers?: ConstWBType<{[layerName: string]: string[]}>;
    class_map?: ConstWBType<{[id: string]: string}>;
    box_score_keys?: ConstWBType<string[]>;
  };
};

export const isImageFileWBType = (t: WBType): t is ImageFileWBType => {
  return t.wb_type === 'wandb.Image' || t.wb_type === 'image-file';
};

export type VideoFileWBType = WBType & {
  wb_type: 'video-file';
};

export const isVideoFileWBType = (t: WBType): t is VideoFileWBType => {
  return t.wb_type === 'video-file';
};

export type AudioFileWBType = WBType & {
  wb_type: 'audio-file';
};

export const isAudioFileWBType = (t: WBType): t is AudioFileWBType => {
  return t.wb_type === 'audio-file';
};

export type HtmlFileWBType = WBType & {
  wb_type: 'html-file';
};

export const isHtmlFileWBType = (t: WBType): t is HtmlFileWBType => {
  return t.wb_type === 'html-file';
};

export type BokehFileWBType = WBType & {
  wb_type: 'bokeh-file';
};

export const isBokehFileWBType = (t: WBType): t is BokehFileWBType => {
  return t.wb_type === 'bokeh-file';
};

export type Object3DFileWBType = WBType & {
  wb_type: 'object3D-file';
};

export const isObject3DFileWBType = (t: WBType): t is Object3DFileWBType => {
  return t.wb_type === 'object3D-file';
};

export type MoleculeFileWBType = WBType & {
  wb_type: 'molecule-file';
};

export const isMoleculeFileWBType = (t: WBType): t is MoleculeFileWBType => {
  return t.wb_type === 'molecule-file';
};

export type PytorchSavedModelWBType = WBType & {
  wb_type: 'pytorch-model-file';
};

export const isPytorchSavedModelWBType = (
  t: WBType
): t is PytorchSavedModelWBType => {
  return t.wb_type === 'pytorch-model-file';
};

export type TimestampWBType = WBType & {
  wb_type: 'timestamp';
};

export const isTimestampWBType = (t: WBType): t is TimestampWBType => {
  return t.wb_type === 'timestamp';
};

export type JoinedTableWBType = WBType & {
  wb_type: 'joined-table';
};

export const isJoinedTableWBType = (t: WBType): t is JoinedTableWBType => {
  return t.wb_type === 'joined-table';
};

export type PartitionedTableWBType = WBType & {
  wb_type: 'partitioned-table';
};

export const isPartitionedTableWBType = (
  t: WBType
): t is PartitionedTableWBType => {
  return t.wb_type === 'partitioned-table';
};

export type WBTraceTreeWBType = WBType & {
  wb_type: 'wb_trace_tree';
};

export const isWBTraceTreeWBType = (t: WBType): t is WBTraceTreeWBType => {
  return t.wb_type === 'wb_trace_tree';
};

export interface MediaTable {
  columns: Array<string | number>;
  data: any[][];
  column_types?: TypedDictWBType;
}

export interface MediaJoinedTable {
  table1: string;
  table2: string;
  join_key: string;
}

export interface MediaPartitionedTable {
  parts_path: string;
}

// export type MediaType =
//   | 'string'
//   | 'number'
//   | 'unknown'
//   | 'boolean'
//   | 'image-file'
//   | 'audio-file'
//   | 'html-file'
//   | 'bokeh-file'
//   | 'object3D-file'
//   | 'molecule-file'
//   | 'pytorch-model-file'
//   | 'video-file';

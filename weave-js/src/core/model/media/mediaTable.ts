import * as _ from 'lodash';

import * as TypeHelpers from '../helpers';
import * as Types from '../types';
import * as WBType from './mediaTypes';

// We treat these specially, for example by automatically
// joining using them.
// TODO: it would be much better to handle this with the type system!
export const SPECIAL_ID_COLUMN_NAMES = ['id', 'uuid'];

export function isIdColumnName(colName: string) {
  return SPECIAL_ID_COLUMN_NAMES.includes(colName.toLowerCase());
}
function valToMediaType(val: any, colName: string | number): Types.Type {
  if (SPECIAL_ID_COLUMN_NAMES.includes(colName.toString())) {
    return 'id';
  } else if (typeof val === 'string' || val === null) {
    return 'string';
  } else if (typeof val === 'number') {
    return 'number';
  } else if (typeof val === 'boolean') {
    return 'boolean';
  } else if (_.isArray(val)) {
    if (val.length === 0) {
      return 'unknown';
    }
    // Use the first entry to determine type
    return {
      type: 'list',
      objectType: valToMediaType(val[0], colName),
    };
  } else if (_.isObject(val)) {
    if (
      // We don't use .type, but some old demo code did and I don't
      // want to break it
      (val as any).type === 'image-file'
    ) {
      return {type: 'image-file'};
    } else if (
      [
        'image-file',
        'video-file',
        'audio-file',
        'html-file',
        'bokeh-file',
        'object3D-file',
        'molecule-file',
        'pytorch-model-file',
        'wb_trace_tree',
      ].includes((val as any)._type)
    ) {
      return {type: (val as any)._type};
    }
  }
  return 'unknown';
}

function wbTypeToMediaType(t: WBType.WBType): Types.Type {
  if (t.wb_type === 'number') {
    return 'number';
  } else if (t.wb_type === 'string') {
    return 'string';
  } else if (t.wb_type === 'boolean') {
    return 'boolean';
  } else if (t.wb_type === 'any') {
    return 'any';
  } else if (t.wb_type === 'none') {
    return 'none';
  } else if (t.wb_type === 'unknown') {
    return 'unknown';
  } else if (t.wb_type === 'invalid') {
    return 'invalid';
  } else if (WBType.isConstWBType(t)) {
    return valToMediaType(t.params.val, '');
  } else if (WBType.isTypedDictWBType(t)) {
    const propertyTypes: {[key: string]: Types.Type} = {};
    const types = t.params.type_map;
    Object.keys(types).forEach(pType => {
      propertyTypes[pType] = wbTypeToMediaType(types[pType]);
    });
    return {
      type: 'typedDict',
      propertyTypes,
    };
  } else if (WBType.isListWBType(t)) {
    if (t.params?.length != null) {
      return TypeHelpers.listWithLength(
        t.params?.length,
        wbTypeToMediaType(t.params.element_type)
      );
    } else {
      return TypeHelpers.list(wbTypeToMediaType(t.params.element_type));
    }
    // TODO: Re-enable
    // } else if (isUnionWBType(t)) {
    //   return {
    //     type: 'union',
    //     members: t.params.allowed_types.map(wbTypeToMediaType),
    //   };
  } else if (WBType.isForeignIndexWBType(t)) {
    // For foreign indexes, they will always be integers. We should treat them as such.
    // TODO: Change this to index type  with a panel eventually?
    return 'number';
  } else if (WBType.isForeignKeyWBType(t)) {
    // For foreign keys, they will always be strings. We should treat them as such.
    // TODO: Change this to foreign key type with a panel eventually?
    return 'string';
  } else if (WBType.isPrimaryKeyWBType(t)) {
    // For primary keys, they will always be strings. We should treat them as such.
    // TODO: Change this to primary key type  with a panel eventually?
    return 'string';
  } else if (WBType.isNDArrayWBType(t)) {
    return {
      type: 'ndarray',
      serializationPath: t.params.serialization_path,
      shape: t.params.shape,
    };
  } else if (WBType.isPythonObjectWBType(t)) {
    // Legacy Class-based types (only applicable "pre-launch")
    if (t.params.class_name === 'Video') {
      return {type: 'video-file'};
    } else if (t.params.class_name === 'Audio') {
      return {type: 'audio-file'};
    } else if (t.params.class_name === 'Html') {
      return {type: 'html-file'};
    } else if (t.params.class_name === 'Bokeh') {
      return {type: 'bokeh-file'};
    } else if (t.params.class_name === 'Object3D') {
      return {type: 'object3D-file'};
    } else if (t.params.class_name === 'Molecule') {
      return {type: 'molecule-file'};
    }
    return 'unknown';
  } else if (WBType.isClassesIdWBType(t)) {
    // This type is not used in the application yet, so returning unknown for now.
    // Honestly, we should remove this type from python client and just use table links
    return 'unknown';
  } else if (WBType.isImageFileWBType(t)) {
    const hasClassInfo = t.params?.class_map?.params?.val != null;
    if (!hasClassInfo) {
      return {
        type: 'image-file',
      };
    } else {
      return {
        type: 'image-file',
        boxLayers: t.params?.box_layers?.params?.val ?? {},
        boxScoreKeys: t.params?.box_score_keys?.params?.val ?? [],
        maskLayers: t.params?.mask_layers?.params?.val ?? {},
        classMap: t.params?.class_map?.params?.val ?? {},
      } as Types.ImageType;
    }
  } else if (WBType.isTableWBType(t)) {
    return {type: 'table', columnTypes: {}};
  } else if (WBType.isVideoFileWBType(t)) {
    return {type: 'video-file'};
  } else if (WBType.isAudioFileWBType(t)) {
    return {type: 'audio-file'};
  } else if (WBType.isHtmlFileWBType(t)) {
    return {type: 'html-file'};
  } else if (WBType.isBokehFileWBType(t)) {
    return {type: 'bokeh-file'};
  } else if (WBType.isObject3DFileWBType(t)) {
    return {type: 'object3D-file'};
  } else if (WBType.isMoleculeFileWBType(t)) {
    return {type: 'molecule-file'};
  } else if (WBType.isPythonObjectWBType(t)) {
    return {type: 'pytorch-model-file'};
  } else if (WBType.isTimestampWBType(t)) {
    return {type: 'timestamp', unit: t.params?.unit || 'ms'};
  } else if (WBType.isWBTraceTreeWBType(t)) {
    return {type: 'wb_trace_tree'};
  } else if (
    WBType.isPartitionedTableWBType(t) ||
    WBType.isJoinedTableWBType(t)
  ) {
    // This should never actually be the case
    return 'unknown';
  } else if (WBType.isUnionWBType(t)) {
    return TypeHelpers.union(t.params.allowed_types.map(wbTypeToMediaType));
  }

  return 'unknown';
}

// wandb <= 0.12.9 did not protect against floating point columns
// when dataframes were used in the construction. This is a small patch
// to fix this mistake at runtime. Fixed in https://github.com/wandb/client/pull/3113
export const tableNeedsFloatColumnConversion = (
  table: WBType.MediaTable
): boolean => {
  return _.isEqual(
    new Set(_.keys(table.column_types?.params?.type_map ?? {})),
    new Set((table.columns ?? []).map(c => `${c}.0`))
  );
};

export const detectColumnTypes = (table: WBType.MediaTable): Types.Type[] => {
  const useFloatConversion = tableNeedsFloatColumnConversion(table);
  const types = table.columns.map((c, i): Types.Type => {
    let res: Types.Type | null = null;
    if (SPECIAL_ID_COLUMN_NAMES.includes(c.toString())) {
      return 'id';
    }
    const typeMapCol = useFloatConversion ? `${c}.0` : c;
    if (table.column_types && table.column_types.params.type_map[typeMapCol]) {
      res = wbTypeToMediaType(table.column_types.params.type_map[typeMapCol]);
    }
    // If we are unable to resolve a type, or it is resolving to an "open" type, infer from data
    if (
      res == null ||
      res === 'unknown' ||
      res === 'any' ||
      (TypeHelpers.isUnion(res) &&
        res.members.some(mem => mem === 'any' || mem === 'unknown'))
    ) {
      if (table.data.length > 0) {
        res = valToMediaType(table.data[0][i], c);
      } else {
        res = 'unknown';
      }
    }
    return res;
  });
  return types;
};

// TODO: agg types are duplicated everywhere
export const agg = (
  type: 'concat' | 'max' | 'min' | 'avg' | undefined,
  data: any[]
) => {
  if (type == null || type === 'concat') {
    return data;
  } else if (type === 'max') {
    return _.max(data);
  } else if (type === 'min') {
    return _.min(data);
  } else {
    return _.sum(data) / data.length;
  }
};

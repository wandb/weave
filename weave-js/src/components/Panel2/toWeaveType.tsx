import {isFunctionType, Type, union} from '@wandb/weave/core';
import _ from 'lodash';

// This is a mapping from JS PanelIDs to their corresponding Python type name
export const panelIdAlternativeMapping: {[jsId: string]: string} = {
  // These are manually defined in Weave1 python panel module.
  table: 'tablePanel',
  number: 'PanelNumber',
  string: 'PanelString',
  boolean: 'PanelBoolean',
  date: 'PanelDate',
  // Below are defined in `panel_legacy.py`
  barchart: 'PanelBarchart',
  'web-viz': 'PanelWebViz',
  'video-file': 'PanelVideoFile',
  'model-file': 'PanelModelFile',
  'id-count': 'PanelIdCount',
  link: 'PanelLink',
  'run-overview': 'PanelRunOverview',
  none: 'PanelNone',
  artifactVersionAliases: 'PanelArtifactVersionAliases',
  artifactVersionTags: 'PanelArtifactVersionTags',
  netron: 'PanelNetron',
  object: 'PanelObject',
  'audio-file': 'PanelAudioFile',
  'string-histogram': 'PanelStringHistogram',
  rawimage: 'PanelRawimage',
  'precomputed-histogram': 'PanelPrecomputedHistogram',
  'image-file-compare': 'PanelImageFileCompare',
  'molecule-file': 'PanelMoleculeFile',
  'multi-histogram': 'PanelMultiHistogram',
  'object3D-file': 'PanelObject3DFile',
  'run-color': 'PanelRunColor',
  'multi-string-histogram': 'PanelMultiStringHistogram',
  dir: 'PanelDir',
  'id-compare-count': 'PanelIdCompareCount',
  jupyter: 'PanelJupyter',
  'bokeh-file': 'PanelBokehFile',
  ndarray: 'PanelNdarray',
  'id-compare': 'PanelIdCompare',
  unknown: 'PanelUnknown',
  'image-file': 'PanelImageFile',
  'project-overview': 'PanelProjectOverview',
  textdiff: 'PanelTextdiff',
  type: 'PanelType',
  text: 'PanelText',
  'string-compare': 'PanelStringCompare',
  'debug-expression-graph': 'PanelDebugExpressionGraph',
  tracer: 'PanelTracer',
};

export function toWeaveType(o: any): any {
  if (o == null) {
    return 'none';
  }

  if (o.domain != null && o.selection != null) {
    // More hacks to properly type nested objects that seem like dicts to
    // js.
    // TODO: Really need to support ObjectType in javascript!
    return {
      type: 'Signals',
      _is_object: true,
      domain: {
        ..._.mapValues(o.domain, toWeaveType),
        type: 'LazyAxisSelections',
        _is_object: true,
      },
      selection: {
        ..._.mapValues(o.selection, toWeaveType),
        type: 'AxisSelections',
        _is_object: true,
      },
    };
  }

  if (o.dims != null && o.constants != null) {
    // More hacks to properly type nested objects that seem like dicts to
    // js.
    // TODO: Really need to support ObjectType in javascript!
    return {
      type: 'Series',
      _is_object: true,
      ..._.mapValues(_.omit(o, ['table', 'constants']), toWeaveType),
      table: {
        type: 'TableState',
        _is_object: true,
        ..._.mapValues(o.table, toWeaveType),
      },
      constants: {
        type: 'PlotConstants',
        _is_object: true,
        ..._.mapValues(o.constants, toWeaveType),
      },
    };
  }
  if (o.columns != null && o.columnNames != null) {
    const res = {
      type: 'TableState',
      _is_object: true,
      ..._.mapValues(o, toWeaveType),
    };
    return res;
  }

  if (o.id != null && o.input_node != null) {
    // Such hacks
    let curPanelId = o.id;

    if (curPanelId == null || curPanelId === '') {
      curPanelId = 'Auto';
    }
    // We have to rename some of the types so to avoid collisions with basic
    // types.
    if (panelIdAlternativeMapping[curPanelId] != null) {
      curPanelId = panelIdAlternativeMapping[curPanelId];
    }

    // This is a panel...
    let configType: Type = 'none';
    if (o.config != null) {
      configType = {
        type: curPanelId + 'Config',
        _is_object: true as any,
        ..._.mapValues(o.config, toWeaveType),
      } as any;
    }
    return {
      type: curPanelId,
      id: 'string',
      _is_object: true,
      _base_type: {type: 'Panel'},
      vars: {
        type: 'typedDict',
        propertyTypes: _.mapValues(o.vars, toWeaveType),
      },
      input_node: toWeaveType(o.input_node),
      config: configType,
      _renderAsPanel: toWeaveType(o.config?._renderAsPanel),
    };
  } else if (o.nodeType != null) {
    if (o.nodeType === 'const' && isFunctionType(o.type)) {
      return o.type;
    }
    return {
      type: 'function',
      inputTypes: {},
      outputType: o.type,
    };
  } else if (_.isArray(o)) {
    return {
      type: 'list',
      objectType: o.length === 0 ? 'unknown' : union(o.map(toWeaveType)),
    };
  } else if (_.isObject(o)) {
    if ('_type' in o) {
      // Conditioned as as part of weaveflow merge
      let oType = (o as {_type: any})._type;
      if (_.isString(oType)) {
        oType = {type: oType};
      }
      return {
        ...oType,
        ..._.mapValues(_.omit(o, ['_type']), toWeaveType),
      };
    }
    return {
      type: 'typedDict',
      propertyTypes: _.mapValues(o, toWeaveType),
    };
  } else if (_.isString(o)) {
    return 'string';
  } else if (_.isNumber(o)) {
    return 'number'; // TODO
  } else if (_.isBoolean(o)) {
    return 'boolean';
  }
  throw new Error('Type conversion not implemented for value: ' + o);
}

import {isFunctionType, Type, union} from '@wandb/weave/core';
import * as _ from 'lodash';
import {panelIdAlternativeMapping} from './PanelGroup';

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
      return {
        type: (o as {_type: any})._type,
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
  throw new Error('Type conversion not implemeneted for value: ' + o);
}

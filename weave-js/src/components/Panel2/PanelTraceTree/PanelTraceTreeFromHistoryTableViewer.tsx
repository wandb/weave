import {
  constString,
  isAssignableTo,
  isConstNode,
  isListLike,
  isOutputNode,
  isTypedDict,
  isTypedDictLike,
  isUnion,
  listObjectType,
  Node,
  nullableTaggable,
  opPick,
  opWBTraceTreeSummary,
  Type,
  typedDict,
  typedDictPropertyTypes,
  union,
  varNode,
  WeaveInterface,
} from '@wandb/weave/core';
import React, {useCallback, useEffect, useMemo} from 'react';
import * as ConfigPanel from '../ConfigPanel';

import {useWeaveContext} from '../../../context';
import * as Panel2 from '../panel';

import {
  PanelTraceTreeTraceTableViewerCommon,
  updateTableState,
} from './panelTraceTreeTableViewerCommon';
import {
  AddColumnEntries,
  addColumnsToTable,
  autoTableColumnExpressions,
  emptyTable,
  getRowExampleNode,
} from '../PanelTable/tableState';
import {useHistory} from 'react-router-dom';

const inputType = {
  type: 'list' as const,
  objectType: {
    type: 'typedDict' as const,
    propertyTypes: {
      // Unfortunately, we don't have a concept of "has at least one key
      // with a certain type" in our type system, so we use a more loosely
      // typed dict here and include a runtime shouldSuggest check.
      // [any_key]: {
      //   type: 'union' as const,
      //   members: [{type: 'wb_trace_tree' as const}, 'none' as const],
      // },
    },
  },
};

type PanelTraceTreeFromHistoryTraceTableViewerConfigType = {
  traceKey: string;
};

type PanelTraceTreeFromHistoryTraceTableViewerProps = Panel2.PanelProps<
  typeof inputType,
  PanelTraceTreeFromHistoryTraceTableViewerConfigType
>;

const isTraceColumnType = (type: Type) => {
  const targetType = {
    type: 'union' as const,
    members: [{type: 'wb_trace_tree' as const}, 'none' as const],
  };
  return (
    !isAssignableTo(type, 'none' as const) && isAssignableTo(type, targetType)
  );
};

const stripType = (rowType: Type) => {
  return nullableTaggable(rowType, innerType => {
    let members = [innerType];
    if (isUnion(innerType)) {
      members = innerType.members;
    }
    members = members.map(member => {
      if (isTypedDict(member)) {
        const propTypes = member.propertyTypes;
        // Filter out underscore keys
        const filteredPropTypes = Object.fromEntries(
          Object.entries(propTypes).filter(
            ([key, keyType]) =>
              !key.startsWith('_') &&
              !key.startsWith('system/') &&
              keyType != null &&
              !isTraceColumnType(keyType)
          )
        );
        return typedDict(filteredPropTypes as any);
      }
      return member;
    });
    return union(members);
  });
};

const makeTableState = (
  inputArrayNode: Node,
  weave: WeaveInterface,
  traceKey: string
) => {
  let ts = emptyTable();
  let columnWidths: {[key: string]: number} = {};
  const exNode = getRowExampleNode(
    ts.preFilterFunction,
    ts.groupBy,
    ts.columnSelectFunctions,
    ts.columnNames,
    ts.order,
    ts.sort,
    inputArrayNode,
    weave
  );
  const modelTraceNode = opWBTraceTreeSummary({
    trace_tree: opPick({
      obj: varNode(exNode.type, 'row'),
      key: constString(traceKey),
    }),
  });
  const {ts: newTs, columnWidths: newColWidth} = updateTableState(
    ts,
    modelTraceNode
  );
  ts = newTs;
  columnWidths = newColWidth;
  const objectType = listObjectType(inputArrayNode.type);
  const allColumns = autoTableColumnExpressions(
    stripType(exNode.type),
    stripType(objectType)
  );

  let addCols: AddColumnEntries = [];
  const columns =
    allColumns.length > 100 ? allColumns.slice(0, 100) : allColumns;
  if (columns.length > 0) {
    addCols = columns.map(colExpr => ({
      selectFn: colExpr,
      keyName: '',
    }));
  }
  ts = addColumnsToTable(ts, addCols).table;

  return {ts, columnWidths};
};

export const PanelTraceTreeFromHistoryTraceTableViewer: React.FC<
  PanelTraceTreeFromHistoryTraceTableViewerProps
> = props => {
  const weave = useWeaveContext();
  const config = props.config;
  const traceKey = config?.traceKey ?? '';
  const tableNode = props.input;
  const {ts, columnWidths} = useMemo(() => {
    return makeTableState(tableNode, weave, traceKey);
  }, [tableNode, traceKey, weave]);
  const traceArrayNode = useMemo(
    () => opPick({obj: props.input, key: constString(traceKey)}),
    [props.input, traceKey]
  );
  const allTracerKeys = useMemo(
    () => getAllTracerKeysFromType(props.input.type),
    [props.input.type]
  );

  useEffect(() => {
    if (config?.traceKey == null && allTracerKeys.length > 0) {
      props.updateConfig({
        traceKey: allTracerKeys[0],
      });
    }
  }, [allTracerKeys, config?.traceKey, props]);

  // This whole thing is a growth hack to point people to the weave app.
  const helpCTALink: string | undefined = useMemo(() => {
    let currNode: Node = tableNode;
    if (traceKey == null) {
      return undefined;
    }
    // TODO get URLs from environment settings, not this
    // hard-coded check
    if (
      !(
        window.location.host === 'app.wandb.ai' ||
        window.location.host === 'app.wandb.test'
      )
    ) {
      return undefined;
    }
    if (!window.location.search.includes('workspace=')) {
      // only show in workspaces
      return undefined;
    }
    const weaveAppBaseURL = window.location.origin.replace('app', 'weave');

    while (isOutputNode(currNode)) {
      if (currNode.fromOp.name === 'project-filteredRuns') {
        const projectNode = currNode.fromOp.inputs.project;
        if (isOutputNode(projectNode)) {
          const entityNameNode = projectNode.fromOp.inputs.entityName;
          const projectNameNode = projectNode.fromOp.inputs.projectName;
          if (isConstNode(entityNameNode) && isConstNode(projectNameNode)) {
            return `${weaveAppBaseURL}/browse/wandb/${entityNameNode.val}/${projectNameNode.val}/run_logged_trace/${traceKey}`;
          }
        }
      } else {
        currNode = Object.values(currNode.fromOp.inputs)[0];
      }
    }
    return undefined;
  }, [tableNode, traceKey]);

  if (config?.traceKey == null) {
    return (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
        Please select a Trace column in the panel's configuration.
      </div>
    );
  }

  return (
    <PanelTraceTreeTraceTableViewerCommon
      tableNode={tableNode}
      traceArrayNode={traceArrayNode}
      initialTableState={ts}
      initialColumnWidths={columnWidths}
      helpCTALink={helpCTALink}
    />
  );
};

export const PanelTraceTreeFromHistoryTraceTableViewerConfigComponent: React.FC<
  PanelTraceTreeFromHistoryTraceTableViewerProps
> = props => {
  const currentSelection = props.config?.traceKey ?? '';
  const allTracerKeys = useMemo(
    () => getAllTracerKeysFromType(props.input.type),
    [props.input.type]
  );
  const setTraceKey = useCallback(
    (traceKey: string) => {
      props.updateConfig({traceKey});
    },
    [props]
  );

  return (
    <ConfigPanel.ConfigOption label="Trace Key">
      <ConfigPanel.ModifiedDropdownConfigField
        selection
        data-test="compare_method"
        scrolling
        multiple={false}
        options={allTracerKeys.map(key => ({
          key,
          text: key,
          value: key,
        }))}
        value={currentSelection}
        onChange={(e, data) => {
          setTraceKey(data.value as any);
        }}
      />
    </ConfigPanel.ConfigOption>
  );
};

const getAllTracerKeysFromType = (nodeInputType: Type): string[] => {
  const keys: string[] = [];
  if (!isListLike(nodeInputType)) {
    return keys;
  }
  nodeInputType = listObjectType(nodeInputType);
  if (!isTypedDictLike(nodeInputType)) {
    return keys;
  }
  const propTypes = typedDictPropertyTypes(nodeInputType);
  for (const [propKey, propType] of Object.entries(propTypes)) {
    if (isTraceColumnType(propType)) {
      keys.push(propKey);
    }
  }
  return keys;
};

export const Spec: Panel2.PanelSpec = {
  id: 'wb_trace_tree-traceDebuggerFromRunHistory',
  displayName: 'LLM Trace Debugger',
  Component: PanelTraceTreeFromHistoryTraceTableViewer,
  ConfigComponent: PanelTraceTreeFromHistoryTraceTableViewerConfigComponent,
  inputType,
  shouldSuggest: nodeInputType => {
    return getAllTracerKeysFromType(nodeInputType).length > 0;
  },
};

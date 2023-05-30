import {
  constNodeUnsafe,
  constString,
  isAssignableTo,
  list,
  listObjectType,
  maybe,
  opDropNa,
  opPick,
  opRunSummary,
  Type,
  typedDict,
  typedDictPropertyTypes,
} from '@wandb/weave/core';
import React from 'react';

import {useNodeWithServerType} from '../../../react';
import * as ConfigPanel from '../ConfigPanel';
import * as Panel2 from '../panel';
import {normalizeTableLike} from '../PanelTable/tableType';

const CUSTOM_TABLE_TYPE = {
  type: 'file' as const,
  wbObjectType: {type: 'table' as const, columnTypes: {}},
};

const inputType = {
  type: 'list' as const,
  objectType: {
    type: 'union' as const,
    members: ['none' as const, 'run' as const],
  },
};

type PanelRunsTableConfigType = {summaryKey: string};

type PanelRunsTableProps = Panel2.PanelProps<
  typeof inputType,
  PanelRunsTableConfigType
>;

const PanelRunsTable: React.FC<PanelRunsTableProps> = props => {
  throw new Error('PanelRunsTable: Cannot be rendered directly');
};

const getKeysFromInputType = (
  inputNodeType?: Type,
  config?: PanelRunsTableConfigType
) => {
  if (
    inputNodeType != null &&
    isAssignableTo(inputNodeType, list(typedDict({})))
  ) {
    const typeMap = typedDictPropertyTypes(listObjectType(inputNodeType));
    const tableKeys = Object.keys(typeMap)
      .filter(key => {
        return isAssignableTo(typeMap[key], maybe(CUSTOM_TABLE_TYPE));
      })
      .sort();
    const value =
      tableKeys.length > 0 &&
      config?.summaryKey != null &&
      tableKeys.indexOf(config?.summaryKey) !== -1
        ? config.summaryKey
        : tableKeys?.[0] ?? '';
    return {tableKeys, value};
  }
  return {tableKeys: [], value: ''};
};

const PanelRunsTableConfig: React.FC<PanelRunsTableProps> = props => {
  const runSummaryNode = opRunSummary({run: props.input});
  const runSummaryRefined = useNodeWithServerType(runSummaryNode);
  const {tableKeys, value} = getKeysFromInputType(
    runSummaryRefined.result?.type,
    props.config
  );
  const options = tableKeys.map(key => ({text: key, value: key}));
  const updateConfig = props.updateConfig;
  const setSummaryKey = React.useCallback(
    val => {
      updateConfig({summaryKey: val});
    },
    [updateConfig]
  );

  return (
    <ConfigPanel.ConfigOption label="Table">
      <ConfigPanel.ModifiedDropdownConfigField
        selection
        data-test="compare_method"
        scrolling
        multiple={false}
        options={options}
        value={value}
        onChange={(e, data) => {
          setSummaryKey(data.value as any);
        }}
      />
    </ConfigPanel.ConfigOption>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'runs-table',
  displayName: 'Run Tables',
  Component: PanelRunsTable,
  ConfigComponent: PanelRunsTableConfig,
  inputType,
  outputType: () => ({
    type: 'list' as const,
    objectType: {
      type: 'list' as const,
      objectType: {type: 'typedDict' as const, propertyTypes: {}},
    },
  }),

  equivalentTransform: async (inputNode, config, refineType) => {
    const expectedReturnType = list(list(typedDict({})));
    const defaultNode = constNodeUnsafe(expectedReturnType, []);
    const runSummaryNode = opRunSummary({run: inputNode as any});
    const runSummaryRefined = await refineType(runSummaryNode);
    const {value} = getKeysFromInputType(runSummaryRefined.type, config);

    const runTableNode = opPick({
      obj: runSummaryNode,
      key: constString(value ?? ''),
    });
    const refinedNode = await refineType(runTableNode);

    if (isAssignableTo(refinedNode.type, list('any'))) {
      const normalizedNode = opDropNa({
        arr: refinedNode,
      });
      const arrNode = normalizeTableLike(normalizedNode);

      const refinedNormalizedNode = await refineType(arrNode);
      // In cases where the resolved type is not assignable to our expected return
      // type, we return the default node instead. The primary case where this
      // happens is when the input list is empty, then the resolved type ends up
      // being a list<none> which does not conform to the output contract
      if (isAssignableTo(refinedNormalizedNode.type, expectedReturnType)) {
        return refinedNormalizedNode;
      }
    }
    return defaultNode;
  },
};

Panel2.registerPanelFunction(
  Spec.id,
  Spec.inputType,
  Spec.equivalentTransform!
);

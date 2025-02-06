import {
  constNodeUnsafe,
  constString,
  isAssignableTo,
  list,
  opDropNa,
  opPick,
  opRunSummary,
  typedDict,
} from '@wandb/weave/core';
import React from 'react';

import {LIST_RUNS_TYPE} from '../../../common/types/run';
import {getTableKeysFromNodeType} from '../../../common/util/table';
import {useNodeWithServerType} from '../../../react';
import * as ConfigPanel from '../ConfigPanel';
import * as Panel2 from '../panel';
import {normalizeTableLike} from '../PanelTable/tableType';

type PanelRunsTableConfigType = {summaryKey: string};

type PanelRunsTableProps = Panel2.PanelProps<
  typeof LIST_RUNS_TYPE,
  PanelRunsTableConfigType
>;

const PanelRunsTable: React.FC<PanelRunsTableProps> = props => {
  throw new Error('PanelRunsTable: Cannot be rendered directly');
};

const PanelRunsTableConfig: React.FC<PanelRunsTableProps> = props => {
  const runSummaryNode = opRunSummary({run: props.input});
  const runSummaryRefined = useNodeWithServerType(runSummaryNode);
  const {tableKeys, value} = getTableKeysFromNodeType(
    runSummaryRefined.result?.type,
    props.config?.summaryKey
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
  inputType: LIST_RUNS_TYPE,
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
    const {value} = getTableKeysFromNodeType(
      runSummaryRefined.type,
      config?.summaryKey
    );

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

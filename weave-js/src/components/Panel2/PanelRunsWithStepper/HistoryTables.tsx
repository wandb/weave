import {LIST_RUNS_TYPE} from '@wandb/weave/common/types/run';
import {opConcat, opRunHistory} from '@wandb/weave/core';
import {useNodeWithServerType} from '@wandb/weave/react';
import React from 'react';

import * as ConfigPanel from '../ConfigPanel';
import * as Panel2 from '../panel';
import {TableSpec} from '../PanelTable/PanelTable';
import {
  buildPanelRunsWithStepper,
  getCurrentTableHistoryKey,
  getTableKeysFromRunsHistoryPropertyType,
  PanelRunsWithStepperConfigType,
  PanelRunsWithStepperProps,
} from './base';

const PanelRunsWithStepperConfig: React.FC<
  PanelRunsWithStepperProps
> = props => {
  const runsHistoryNode = opConcat({
    arr: opRunHistory({run: props.input as any}),
  });
  const runsHistoryRefined = useNodeWithServerType(runsHistoryNode);
  const tableKeys = getTableKeysFromRunsHistoryPropertyType(
    runsHistoryRefined.result?.type
  );
  const tableHistoryKey = getCurrentTableHistoryKey(
    tableKeys,
    props.config?.tableHistoryKey
  );

  const options = tableKeys.map(key => ({text: key, value: key}));
  const updateConfig = props.updateConfig;
  const setTableHistoryKey = React.useCallback(
    val => {
      updateConfig({tableHistoryKey: val});
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
        value={tableHistoryKey}
        onChange={(e, data) => {
          setTableHistoryKey(data.value as any);
        }}
      />
    </ConfigPanel.ConfigOption>
  );
};

export const Spec: Panel2.PanelSpec<PanelRunsWithStepperConfigType> = {
  id: 'run-history-tables-stepper',
  displayName: 'Run History Tables Stepper',
  Component: buildPanelRunsWithStepper(TableSpec),
  ConfigComponent: PanelRunsWithStepperConfig,
  inputType: LIST_RUNS_TYPE,
  outputType: () => ({
    type: 'list' as const,
    objectType: {
      type: 'list' as const,
      objectType: {type: 'typedDict' as const, propertyTypes: {}},
    },
  }),
};

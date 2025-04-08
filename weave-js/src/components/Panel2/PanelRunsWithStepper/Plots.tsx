import {LIST_RUNS_TYPE} from '@wandb/weave/common/types/run';
import {
  constFunction,
  constNumber,
  constString,
  isVoidNode,
  NodeOrVoidNode,
  opConcat,
  opFileTable,
  opFilter,
  opIndex,
  opNumberEqual,
  opPick,
  opRunHistory,
  opTableRows,
  voidNode,
} from '@wandb/weave/core';
import {useNodeWithServerType} from '@wandb/weave/react';
import React from 'react';

import * as ConfigPanel from '../ConfigPanel';
import * as Panel2 from '../panel';
import {PanelComp2} from '../PanelComp';
import {Spec as PlotSpec} from '../PanelPlot/PanelPlot';
import {
  buildPanelRunsWithStepper,
  getCurrentTableHistoryKey,
  getTableKeysFromRunsHistoryPropertyType,
  PanelRunsWithStepperConfigType,
  PanelRunsWithStepperProps,
} from './base';

const PanelRunsPlotsWithStepperConfig: React.FC<
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

  const exampleRow = opIndex({
    arr: runsHistoryNode,
    index: constNumber(0),
  });
  const exampleRowRefined = useNodeWithServerType(exampleRow);
  let defaultNode: NodeOrVoidNode = voidNode();
  if (
    props.config != null &&
    props.config.currentStep != null &&
    props.config.currentStep >= 0 &&
    tableHistoryKey
  ) {
    defaultNode = opTableRows({
      table: opFileTable({
        file: opPick({
          obj: opFilter({
            arr: runsHistoryNode,
            filterFn: constFunction(
              {row: exampleRowRefined.result.type},
              ({row}) =>
                opNumberEqual({
                  lhs: opPick({obj: row, key: constString('_step')}),
                  rhs: constNumber(props.config!.currentStep),
                })
            ),
          }),
          key: constString(tableHistoryKey),
        }),
      }),
    });
  }

  return (
    <>
      <ConfigPanel.ConfigSection>
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
      </ConfigPanel.ConfigSection>
      <ConfigPanel.ConfigSection>
        {defaultNode != null && !isVoidNode(defaultNode) && (
          <PanelComp2
            input={defaultNode}
            inputType={defaultNode.type}
            loading={props.loading}
            panelSpec={PlotSpec}
            configMode={true}
            config={props.config}
            context={props.context}
            updateConfig={props.updateConfig}
            updateContext={props.updateContext}
            updateInput={props.updateInput}
          />
        )}
      </ConfigPanel.ConfigSection>
    </>
  );
};

export const Spec: Panel2.PanelSpec<PanelRunsWithStepperConfigType> = {
  id: 'run-history-plots-stepper',
  displayName: 'Run History Plots Stepper',
  Component: buildPanelRunsWithStepper(PlotSpec),
  ConfigComponent: PanelRunsPlotsWithStepperConfig,
  inputType: LIST_RUNS_TYPE,
  outputType: () => ({
    type: 'list' as const,
    objectType: {
      type: 'list' as const,
      objectType: {type: 'typedDict' as const, propertyTypes: {}},
    },
  }),
};

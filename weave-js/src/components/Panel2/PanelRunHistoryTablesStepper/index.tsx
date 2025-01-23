import SliderInput from '@wandb/weave/common/components/elements/SliderInput';
import {
  constFunction,
  constNodeUnsafe,
  constNumber,
  constString,
  file,
  isAssignableTo,
  list,
  listObjectType,
  maybe,
  NodeOrVoidNode,
  opDict,
  opFileTable,
  opIndex,
  opMap,
  opPick,
  opRunHistory,
  opTableRows,
  Type,
  typedDict,
  typedDictPropertyTypes,
  voidNode,
} from '@wandb/weave/core';
import React, {useEffect, useState} from 'react';

import {useNodeValue, useNodeWithServerType} from '../../../react';
import * as ConfigPanel from '../ConfigPanel';
import * as Panel2 from '../panel';
import {PanelComp2} from '../PanelComp';
import {TableSpec} from '../PanelTable/PanelTable';

const CUSTOM_TABLE_TYPE = {
  type: 'file' as const,
  wbObjectType: {type: 'table' as const, columnTypes: {}},
};

const LIST_RUNS_INPUT_TYPE = {
  type: 'list' as const,
  objectType: {
    type: 'union' as const,
    members: ['none' as const, 'run' as const],
  },
};

type PanelRunsHistoryTablesConfigType = {
  tableHistoryKey: string;
};

type PanelRunHistoryTablesStepperProps = Panel2.PanelProps<
  typeof LIST_RUNS_INPUT_TYPE,
  PanelRunsHistoryTablesConfigType
>;

const getKeysFromInputType = (
  inputNodeType?: Type,
  config?: PanelRunsHistoryTablesConfigType
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
      config?.tableHistoryKey != null &&
      tableKeys.indexOf(config?.tableHistoryKey) !== -1
        ? config.tableHistoryKey
        : tableKeys?.[0] ?? '';
    return {tableKeys, value};
  }
  return {tableKeys: [], value: ''};
};

const PanelRunHistoryTablesStepperConfig: React.FC<
  PanelRunHistoryTablesStepperProps
> = props => {
  const firstRun = opIndex({arr: props.input, index: constNumber(0)});
  const runHistoryNode = opRunHistory({run: firstRun as any});
  const runHistoryRefined = useNodeWithServerType(runHistoryNode);
  const {tableKeys, value} = getKeysFromInputType(
    runHistoryRefined.result?.type,
    props.config
  );
  const options = tableKeys.map(key => ({text: key, value: key}));
  const updateConfig = props.updateConfig;
  const setSummaryKey = React.useCallback(
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
        value={value}
        onChange={(e, data) => {
          setSummaryKey(data.value as any);
        }}
      />
    </ConfigPanel.ConfigOption>
  );
};

const PanelRunHistoryTablesStepper: React.FC<
  PanelRunHistoryTablesStepperProps
> = props => {
  const [currentStep, setCurrentStep] = useState(0);
  const [currentTableHistoryKey, setCurrentTableHistoryKey] =
    useState<any>(null);
  const [steps, setSteps] = useState<number[]>([]);
  const [tables, setTables] = useState<any[]>([]);

  const {input, config} = props;
  const firstRun = opIndex({arr: input, index: constNumber(0)});
  const runHistoryNode = opRunHistory({run: firstRun as any});
  const runHistoryRefined = useNodeWithServerType(runHistoryNode);
  const {value} = getKeysFromInputType(runHistoryRefined.result?.type, config);
  const tableWithStepsNode = opMap({
    arr: runHistoryRefined.result,
    mapFn: constFunction({row: runHistoryRefined.result.type}, ({row}) =>
      opDict({
        _step: opPick({obj: row, key: constString('_step')}),
        table: opPick({obj: row, key: constString(value ?? '')}),
      })
    ) as any,
  });

  const {
    result: tablesWithStepsNodeResult,
    loading: tablesWithStepsNodeLoading,
  } = useNodeValue(tableWithStepsNode, {
    skip: !value || currentTableHistoryKey === value,
  });

  useEffect(() => {
    if (tablesWithStepsNodeLoading) {
      return;
    }

    if (tablesWithStepsNodeResult != null) {
      const steps = tablesWithStepsNodeResult.map(row => row._step);
      const tables = tablesWithStepsNodeResult.map(row => row.table);
      setSteps(steps);
      setCurrentStep(steps[0]);
      setCurrentTableHistoryKey(value);
      setTables(tables);
    }
  }, [tablesWithStepsNodeResult, tablesWithStepsNodeLoading, value]);

  const tableIndex = steps.indexOf(currentStep);
  let defaultNode: NodeOrVoidNode = voidNode();
  if (tableIndex !== -1) {
    defaultNode = opTableRows({
      table: opFileTable({
        file: constNodeUnsafe(
          file('json', {type: 'table', columnTypes: {}}),
          tables[tableIndex]
        ),
      }),
    });
  }

  return (
    <>
      {defaultNode != null && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            width: '100%',
            height: '100%',
            padding: '2px',
            overflowY: 'auto',
          }}>
          <PanelComp2
            input={defaultNode}
            inputType={defaultNode.type}
            loading={props.loading}
            panelSpec={TableSpec}
            configMode={false}
            config={config}
            context={props.context}
            updateConfig={props.updateConfig}
            updateContext={props.updateContext}
            updateInput={props.updateInput}
          />
          {steps.length > 0 && (
            <div
              style={{
                padding: '2px',
                height: '1.7em',
                borderTop: '1px solid #ddd',
                backgroundColor: '#f8f8f8',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
              }}>
              <SliderInput
                min={steps[0]}
                max={steps[steps.length - 1]}
                minLabel={steps[0].toString()}
                maxLabel={steps[steps.length - 1].toString()}
                hasInput={true}
                value={currentStep}
                step={1}
                ticks={steps}
                onChange={setCurrentStep}
              />
            </div>
          )}
        </div>
      )}
    </>
  );
};

export const Spec: Panel2.PanelSpec<PanelRunsHistoryTablesConfigType> = {
  id: 'run-history-tables-stepper',
  displayName: 'Run History Tables Stepper',
  Component: PanelRunHistoryTablesStepper,
  ConfigComponent: PanelRunHistoryTablesStepperConfig,
  inputType: LIST_RUNS_INPUT_TYPE,
  outputType: () => ({
    type: 'list' as const,
    objectType: {
      type: 'list' as const,
      objectType: {type: 'typedDict' as const, propertyTypes: {}},
    },
  }),
};

Panel2.registerPanelFunction(
  Spec.id,
  LIST_RUNS_INPUT_TYPE,
  Spec.equivalentTransform!
);

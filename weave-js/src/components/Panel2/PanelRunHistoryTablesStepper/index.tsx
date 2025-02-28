import SliderInput from '@wandb/weave/common/components/elements/SliderInput';
import {TABLE_FILE_TYPE} from '@wandb/weave/common/types/file';
import {
  constFunction,
  constNumber,
  constString,
  isAssignableTo,
  isUnion,
  listObjectType,
  maybe,
  NodeOrVoidNode,
  nullableTaggableValue,
  opConcat,
  opFileTable,
  opFilter,
  opIndex,
  opNumberEqual,
  opPick,
  opRunHistory,
  opTableRows,
  Type,
  typedDictPropertyTypes,
  Union,
  voidNode,
} from '@wandb/weave/core';
import React, {useEffect, useState} from 'react';

import {LIST_RUNS_TYPE} from '../../../common/types/run';
import {useNodeValue, useNodeWithServerType} from '../../../react';
import * as ConfigPanel from '../ConfigPanel';
import * as Panel2 from '../panel';
import {PanelComp2} from '../PanelComp';
import {TableSpec} from '../PanelTable/PanelTable';

type PanelRunsHistoryTablesConfigType = {
  tableHistoryKey: string;
};

type PanelRunHistoryTablesStepperProps = Panel2.PanelProps<
  typeof LIST_RUNS_TYPE,
  PanelRunsHistoryTablesConfigType
>;

const getTableKeysFromRunsHistoryPropertyType = (
  runsHistoryPropertyType: Type | undefined
) => {
  if (
    runsHistoryPropertyType &&
    isUnion(nullableTaggableValue(listObjectType(runsHistoryPropertyType)))
  ) {
    const runsPropertyType: Union = nullableTaggableValue(
      listObjectType(runsHistoryPropertyType)
    ) as Union;
    const tableKeys = runsPropertyType.members.reduce(
      (acc: string[], member: Type) => {
        const typeMap = typedDictPropertyTypes(member);
        const runTableKeys = Object.keys(typeMap).filter(key => {
          return isAssignableTo(typeMap[key], maybe(TABLE_FILE_TYPE));
        });

        return [...acc, ...runTableKeys];
      },
      []
    );
    return [...new Set(tableKeys)].sort();
  }
  return [];
};

const getCurrentTableHistoryKey = (
  tableKeys: string[],
  configKey: string | undefined
) => {
  if (configKey && tableKeys.indexOf(configKey) !== -1) {
    return configKey;
  } else if (tableKeys.length > 0) {
    return tableKeys[0];
  }
  return '';
};

const PanelRunHistoryTablesStepperConfig: React.FC<
  PanelRunHistoryTablesStepperProps
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

const PanelRunHistoryTablesStepper: React.FC<
  PanelRunHistoryTablesStepperProps
> = props => {
  const [currentStep, setCurrentStep] = useState(0);
  const [steps, setSteps] = useState<number[]>([]);
  const {input} = props;

  const runsHistoryNode = opConcat({
    arr: opRunHistory({run: input as any}),
  });
  const runsHistoryRefined = useNodeWithServerType(runsHistoryNode);
  const tableKeys = getTableKeysFromRunsHistoryPropertyType(
    runsHistoryRefined.result?.type
  );
  const tableHistoryKey = getCurrentTableHistoryKey(
    tableKeys,
    props.config?.tableHistoryKey
  );

  const stepsNode = opPick({
    obj: runsHistoryNode,
    key: constString('_step'),
  });
  const {result: stepsNodeResult, loading: stepsNodeLoading} =
    useNodeValue(stepsNode);

  useEffect(() => {
    if (stepsNodeLoading) {
      return;
    }

    if (stepsNodeResult != null) {
      const newSteps: number[] = [...new Set<number>(stepsNodeResult)].sort(
        (a, b) => a - b
      );
      setSteps(newSteps);
      setCurrentStep(newSteps[0]);
    }
  }, [stepsNodeResult, stepsNodeLoading]);

  const exampleRow = opIndex({
    arr: runsHistoryNode,
    index: constNumber(0),
  });
  const exampleRowRefined = useNodeWithServerType(exampleRow);
  let defaultNode: NodeOrVoidNode = voidNode();
  if (currentStep) {
    // This performs the following weave expression:
    // runs.history.concat.filter((row) => row._step == <current-step>)[<table-history-key>].concat
    defaultNode = opConcat({
      arr: opTableRows({
        table: opFileTable({
          file: opPick({
            obj: opFilter({
              arr: runsHistoryNode,
              filterFn: constFunction(
                {row: exampleRowRefined.result.type},
                ({row}) =>
                  opNumberEqual({
                    lhs: opPick({obj: row, key: constString('_step')}),
                    rhs: constNumber(currentStep),
                  })
              ),
            }),
            key: constString(tableHistoryKey),
          }),
        }),
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
            config={props.config}
            context={props.context}
            updateConfig={props.updateConfig}
            updateContext={props.updateContext}
            updateInput={props.updateInput}
          />
          {steps.length > 0 && (
            <div
              style={{
                padding: '8px',
                borderTop: '1px solid #ddd',
                backgroundColor: '#f8f8f8',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                marginTop: '8px',
              }}>
              Step:{' '}
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
  inputType: LIST_RUNS_TYPE,
  outputType: () => ({
    type: 'list' as const,
    objectType: {
      type: 'list' as const,
      objectType: {type: 'typedDict' as const, propertyTypes: {}},
    },
  }),
};

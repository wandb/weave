import SliderInput from '@wandb/weave/common/components/elements/SliderInput';
import {TABLE_FILE_TYPE} from '@wandb/weave/common/types/file';
import {getTableKeysFromNodeType} from '@wandb/weave/common/util/table';
import {
  constFunction,
  constNumber,
  constString,
  isAssignableTo,
  isUnion,
  isVoidNode,
  list,
  listObjectType,
  maybe,
  Node,
  NodeOrVoidNode,
  nullableTaggableValue,
  opConcat,
  opFileTable,
  opFilter,
  opIndex,
  opIsNone,
  opNot,
  opNumberEqual,
  opPick,
  opRunHistory,
  opTableRows,
  Type,
  typedDict,
  typedDictPropertyTypes,
  Union,
  union,
  voidNode,
} from '@wandb/weave/core';
import React, {useEffect} from 'react';

import {LIST_RUNS_TYPE} from '../../../common/types/run';
import {useNodeValue, useNodeWithServerType} from '../../../react';
import * as ConfigPanel from '../ConfigPanel';
import * as Panel2 from '../panel';
import {PanelComp2} from '../PanelComp';
export type PanelRunsWithStepperConfigType = {
  tableHistoryKey: string;
  currentStep: number;
  steps: number[];
};

export type PanelRunsWithStepperProps = Panel2.PanelProps<
  typeof LIST_RUNS_TYPE,
  PanelRunsWithStepperConfigType
>;

export const getTableKeysFromRunsHistoryPropertyType = (
  runsHistoryPropertyType: Type | undefined
) => {
  // Case where keys across runs vary (hence the union)
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

  // Case where keys across runs are the same
  if (runsHistoryPropertyType) {
    const {tableKeys} = getTableKeysFromNodeType(runsHistoryPropertyType);
    return tableKeys.sort();
  }

  return [];
};

export const getCurrentTableHistoryKey = (
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

export const convertInput = (input: Node) => {
  if (isAssignableTo(input.type, LIST_RUNS_TYPE)) {
    return opConcat({
      arr: opRunHistory({run: input as any}),
    });
  }

  if (isAssignableTo(input.type, list(list(union([typedDict({})]))))) {
    return opConcat({
      arr: input as any,
    });
  }

  return input;
};

export const buildPanelRunsWithStepper = (
  spec: Panel2.PanelSpec
): React.FC<PanelRunsWithStepperProps> => {
  const PanelRunsWithStepperInner: React.FC<
    PanelRunsWithStepperProps
  > = props => {
    const {input, updateConfig, config} = props;

    const safeUpdateConfig = React.useCallback(
      (updates: Partial<PanelRunsWithStepperConfigType>) => {
        const needsUpdate = Object.entries(updates).some(
          ([key, value]) => (config as any)?.[key] !== value
        );

        if (needsUpdate) {
          updateConfig(updates);
        }
      },
      [config, updateConfig]
    );

    const convertedInput = convertInput(input);
    const convertedInputRefined = useNodeWithServerType(convertedInput);
    const tableKeys = getTableKeysFromRunsHistoryPropertyType(
      convertedInputRefined.result?.type
    );
    const tableHistoryKey = getCurrentTableHistoryKey(
      tableKeys,
      props.config?.tableHistoryKey
    );

    // runs.history.concat.filter((row) => !row[<table-history-key>].isNone)
    const filteredRunsHistoryNode = opFilter({
      arr: convertedInput,
      filterFn: constFunction({row: convertedInput.type}, ({row}) =>
        opNot({
          bool: opIsNone({
            val: opPick({obj: row, key: constString(tableHistoryKey)}),
          }),
        })
      ),
    });

    // runs.history.concat.filter((row) => !row[<table-history-key>].isNone)["_step"]
    const stepsNode = opPick({
      obj: filteredRunsHistoryNode,
      key: constString('_step'),
    });
    const {result: stepsNodeResult, loading: stepsNodeLoading} =
      useNodeValue(stepsNode);

    useEffect(() => {
      if (stepsNodeLoading || stepsNodeResult == null) {
        return;
      }

      const newSteps: number[] = [...new Set<number>(stepsNodeResult)].sort(
        (a, b) => a - b
      );

      const currentConfigSteps = config?.steps;

      const hasStepsChanged =
        currentConfigSteps === undefined ||
        currentConfigSteps.length !== newSteps.length ||
        !currentConfigSteps.every((step, i) => step === newSteps[i]);

      if (hasStepsChanged) {
        safeUpdateConfig({steps: newSteps});
      }

      const configCurrentStep = config?.currentStep ?? -1;
      const shouldUpdateCurrentStep =
        hasStepsChanged ||
        configCurrentStep === undefined ||
        configCurrentStep < 0 ||
        !newSteps.includes(configCurrentStep);

      if (shouldUpdateCurrentStep) {
        safeUpdateConfig({currentStep: newSteps[0]});
      }
    }, [stepsNodeResult, stepsNodeLoading, config, safeUpdateConfig]);

    const exampleRow = opIndex({
      arr: convertedInput,
      index: constNumber(0),
    });
    const exampleRowRefined = useNodeWithServerType(exampleRow);
    let defaultNode: NodeOrVoidNode = voidNode();
    const currentStep = config?.currentStep ?? -1;
    if (currentStep != null && currentStep >= 0 && tableHistoryKey) {
      // This performs the following weave expression:
      // runs.history.concat.filter((row) => row._step == <current-step>)[<table-history-key>].concat
      defaultNode = opConcat({
        arr: opTableRows({
          table: opFileTable({
            file: opPick({
              obj: opFilter({
                arr: convertedInput,
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
        {defaultNode != null && !isVoidNode(defaultNode) && (
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
              panelSpec={spec}
              configMode={false}
              config={props.config}
              context={props.context}
              updateConfig={props.updateConfig}
              updateContext={props.updateContext}
              updateInput={props.updateInput}
            />
            {(config?.steps?.length || 0) > 0 && (
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
                  min={config!.steps![0]}
                  max={config!.steps![config!.steps!.length - 1]}
                  minLabel={config!.steps![0].toString()}
                  maxLabel={config!.steps![
                    config!.steps!.length - 1
                  ].toString()}
                  hasInput={true}
                  value={config!.currentStep!}
                  step={1}
                  ticks={config!.steps}
                  onChange={val => {
                    safeUpdateConfig({currentStep: val});
                  }}
                />
              </div>
            )}
          </div>
        )}
      </>
    );
  };

  return PanelRunsWithStepperInner;
};

const PanelStepperConfig: React.FC<PanelRunsWithStepperProps> = props => {
  const convertedInput = convertInput(props.input);
  const convertedInputRefined = useNodeWithServerType(convertedInput);

  const tableKeys = getTableKeysFromRunsHistoryPropertyType(
    convertedInputRefined.result?.type
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

const PanelStepperConvert: React.FC<PanelRunsWithStepperProps> = props => {
  const {input, updateConfig, config} = props;

  const safeUpdateConfig = React.useCallback(
    (updates: Partial<PanelRunsWithStepperConfigType>) => {
      const needsUpdate = Object.entries(updates).some(
        ([key, value]) => (config as any)?.[key] !== value
      );

      if (needsUpdate) {
        updateConfig(updates);
      }
    },
    [config, updateConfig]
  );

  const convertedInput = convertInput(input);
  const convertedInputRefined = useNodeWithServerType(convertedInput);
  const tableKeys = getTableKeysFromRunsHistoryPropertyType(
    convertedInputRefined.result?.type
  );
  const tableHistoryKey = getCurrentTableHistoryKey(
    tableKeys,
    props.config?.tableHistoryKey
  );

  // runs.history.concat.filter((row) => !row[<table-history-key>].isNone)
  const filteredRunsHistoryNode = opFilter({
    arr: convertedInput,
    filterFn: constFunction({row: convertedInput.type}, ({row}) =>
      opNot({
        bool: opIsNone({
          val: opPick({obj: row, key: constString(tableHistoryKey)}),
        }),
      })
    ),
  });

  // runs.history.concat.filter((row) => !row[<table-history-key>].isNone)["_step"]
  const stepsNode = opPick({
    obj: filteredRunsHistoryNode,
    key: constString('_step'),
  });
  const {result: stepsNodeResult, loading: stepsNodeLoading} =
    useNodeValue(stepsNode);

  useEffect(() => {
    if (stepsNodeLoading || stepsNodeResult == null) {
      return;
    }

    const newSteps: number[] = [...new Set<number>(stepsNodeResult)].sort(
      (a, b) => a - b
    );

    const currentConfigSteps = config?.steps;

    const hasStepsChanged =
      currentConfigSteps === undefined ||
      currentConfigSteps.length !== newSteps.length ||
      !currentConfigSteps.every((step, i) => step === newSteps[i]);

    if (hasStepsChanged) {
      safeUpdateConfig({steps: newSteps});
    }

    const configCurrentStep = config?.currentStep ?? -1;
    const shouldUpdateCurrentStep =
      hasStepsChanged ||
      configCurrentStep === undefined ||
      configCurrentStep < 0 ||
      !newSteps.includes(configCurrentStep);

    if (shouldUpdateCurrentStep) {
      safeUpdateConfig({currentStep: newSteps[0]});
    }
  }, [stepsNodeResult, stepsNodeLoading, config, safeUpdateConfig]);

  const exampleRow = opIndex({
    arr: convertedInput,
    index: constNumber(0),
  });
  const exampleRowRefined = useNodeWithServerType(exampleRow);
  let defaultNode: NodeOrVoidNode = voidNode();
  const currentStep = config?.currentStep ?? -1;
  if (currentStep != null && currentStep >= 0 && tableHistoryKey) {
    // This performs the following weave expression:
    // runs.history.concat.filter((row) => row._step == <current-step>)[<table-history-key>].concat
    defaultNode = opConcat({
      arr: opTableRows({
        table: opFileTable({
          file: opPick({
            obj: opFilter({
              arr: convertedInput,
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
      {defaultNode != null && !isVoidNode(defaultNode) && (
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
            panelSpec={props.child}
            configMode={false}
            config={props.config}
            context={props.context}
            updateConfig={props.updateConfig}
            updateContext={props.updateContext}
            updateInput={props.updateInput}
          />
          {(config?.steps?.length || 0) > 0 && (
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
                min={config!.steps![0]}
                max={config!.steps![config!.steps!.length - 1]}
                minLabel={config!.steps![0].toString()}
                maxLabel={config!.steps![config!.steps!.length - 1].toString()}
                hasInput={true}
                value={config!.currentStep!}
                step={1}
                ticks={config!.steps}
                onChange={val => {
                  safeUpdateConfig({currentStep: val});
                }}
              />
            </div>
          )}
        </div>
      )}
    </>
  );
};

export const StepperSpec: Panel2.PanelConvertSpec<PanelRunsWithStepperConfigType> =
  {
    id: 'stepper',
    displayName: 'Stepper',
    Component: PanelStepperConvert,
    ConfigComponent: PanelStepperConfig,
    convert: (inputType: Type) => {
      if (
        isAssignableTo(inputType, LIST_RUNS_TYPE) ||
        isAssignableTo(inputType, list(list(union([typedDict({})])))) ||
        isAssignableTo(inputType, list(typedDict({})))
      ) {
        return list(typedDict({}));
      }
      return null;
    },
  };

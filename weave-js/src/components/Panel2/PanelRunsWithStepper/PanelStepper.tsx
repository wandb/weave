import SliderInput from '@wandb/weave/common/components/elements/SliderInput';
import {
  constFunction,
  constNumber,
  constString,
  isAssignableTo,
  isListLike,
  isUnion,
  isVoidNode,
  list,
  listObjectType,
  Node,
  NodeOrVoidNode,
  opConcat,
  opFilter,
  opIndex,
  opIsNone,
  opNot,
  opNumberEqual,
  opPick,
  opRunHistory,
  Type,
  typedDict,
  typedDictPropertyTypes,
  union,
  voidNode,
} from '@wandb/weave/core';
import React, {useEffect, useMemo} from 'react';

import {LIST_RUNS_TYPE} from '../../../common/types/run';
import {useNodeValue, useNodeWithServerType} from '../../../react';
import {PanelStack, usePanelStacksForType} from '../availablePanels';
import {ModifiedDropdownConfigField} from '../ConfigPanel';
import {ConfigOption} from '../ConfigPanel';
import * as Panel2 from '../panel';
import {PanelComp2} from '../PanelComp';

export type PanelStepperConfigType = {
  currentStep: number;
  steps: number[];
  workingPanelId: string | undefined;
  workingKeyAndType: {key: string; type: Type};
  workingSliderKey: string | null;
};

const LIST_ANY_TYPE = {
  type: 'list' as const,
  objectType: 'any' as const,
};

export type PanelStepperProps = Panel2.PanelProps<
  typeof LIST_ANY_TYPE,
  PanelStepperConfigType
>;

const getDefaultWorkingKeyAndType = (
  inputType: Type,
  config: PanelStepperConfigType | undefined
) => {
  const keysAndTypes = getKeysAndTypesFromPropertyType(inputType);
  const defaultKey =
    config?.workingKeyAndType?.key &&
    config.workingKeyAndType.key in keysAndTypes
      ? config.workingKeyAndType.key
      : Object.keys(keysAndTypes)[0] ?? '';
  return {
    key: defaultKey,
    type: keysAndTypes[defaultKey] ?? null,
  };
};

const getKeysAndTypesFromPropertyType = (
  propertyType: Type | undefined
): {[key: string]: Type} => {
  if (propertyType == null) {
    return {};
  }

  if (isAssignableTo(propertyType, list(typedDict({})))) {
    return typedDictPropertyTypes(listObjectType(propertyType));
  }

  if (isUnion(propertyType)) {
    return propertyType.members.reduce(
      (acc: {[key: string]: Type}, member: Type) => {
        const memberKeysAndTypes = getKeysAndTypesFromPropertyType(member);
        return {...acc, ...memberKeysAndTypes};
      },
      {}
    );
  }

  if (isListLike(propertyType)) {
    return getKeysAndTypesFromPropertyType(listObjectType(propertyType));
  }

  return {};
};

const convertInputNode = (inputNode: Node) => {
  if (isAssignableTo(inputNode.type, LIST_RUNS_TYPE)) {
    return opConcat({arr: opRunHistory({run: inputNode as any})});
  }
  if (isAssignableTo(inputNode.type, list(list(union([typedDict({})]))))) {
    return opConcat({arr: inputNode as any});
  }
  return inputNode;
};

const safeUpdateConfigThunk =
  (
    config: PanelStepperConfigType | undefined,
    updateConfig: (updates: Partial<PanelStepperConfigType>) => void
  ) =>
  (updates: Partial<PanelStepperConfigType>) => {
    const needsUpdate = Object.entries(updates).some(
      ([key, value]) => (config as any)?.[key] !== value
    );

    if (needsUpdate) {
      updateConfig(updates);
    }
  };

export const PanelStepperConfig: React.FC<PanelStepperProps> = props => {
  const {input, updateConfig, config} = props;

  const keysAndTypes = useMemo(
    () => getKeysAndTypesFromPropertyType(input.type),
    [input.type]
  );

  // TODO (nicholaspun-wandb): Used for the "Slider Key" config option below
  // const sliderKeys = useMemo(
  //   () =>
  //     Object.keys(keysAndTypes).filter(key =>
  //       isAssignableTo(keysAndTypes[key], 'number')
  //     ),
  //   [keysAndTypes]
  // );

  const safeUpdateConfig = React.useCallback(
    (updates: Partial<PanelStepperConfigType>) =>
      safeUpdateConfigThunk(config, updateConfig)(updates),
    [config, updateConfig]
  );

  const defaultKeyAndType = getDefaultWorkingKeyAndType(input.type, config);

  if (config?.workingKeyAndType == null) {
    safeUpdateConfig({
      workingKeyAndType: defaultKeyAndType,
    });
  }

  const {stackIds} = usePanelStacksForType(
    defaultKeyAndType.type,
    config?.workingPanelId ?? undefined
  );

  if (config?.workingPanelId == null) {
    safeUpdateConfig({
      workingPanelId: stackIds[0].id,
    });
  }

  return (
    <>
      {/*
      TODO (nicholaspun-wandb): This technically works, but slider keys that aren't integral
      numbers don't work well.

      <ConfigOption label="Slider Key">
        <ModifiedDropdownConfigField
          selection
          search
          disabled={props.loading}
          scrolling
          item
          direction="left"
          options={sliderKeys.map(key => ({
            key,
            value: key,
            text: key,
          }))}
          value={config?.workingSliderKey ?? '_step'}
          onChange={(e, {value}) =>
            safeUpdateConfig({workingSliderKey: value as string})
          }
        />
      </ConfigOption> 
      
      */}
      <ConfigOption label="Property Key">
        <ModifiedDropdownConfigField
          selection
          search
          disabled={props.loading}
          scrolling
          item
          direction="left"
          options={Object.keys(keysAndTypes).map(key => ({
            key,
            value: key,
            text: key,
          }))}
          value={defaultKeyAndType.key}
          onChange={(e, {value}) => {
            safeUpdateConfig({
              workingKeyAndType: {
                key: value as string,
                type: keysAndTypes[value as string],
              },
              workingPanelId: undefined,
            });
          }}
        />
      </ConfigOption>
      <ConfigOption label="Panel Type">
        <ModifiedDropdownConfigField
          selection
          search
          disabled={props.loading}
          scrolling
          item
          direction="left"
          options={stackIds.map(si => ({
            text: si.displayName,
            value: si.id,
          }))}
          value={config?.workingPanelId}
          onChange={(e, {value}) =>
            safeUpdateConfig({workingPanelId: value as string})
          }
        />
      </ConfigOption>
    </>
  );
};

export const PanelStepper: React.FC<PanelStepperProps> = props => {
  const {input, updateConfig, config} = props;

  const safeUpdateConfig = React.useCallback(
    (updates: Partial<PanelStepperConfigType>) =>
      safeUpdateConfigThunk(config, updateConfig)(updates),
    [config, updateConfig]
  );

  const workingKeyAndType = getDefaultWorkingKeyAndType(input.type, config);
  const workingKey = workingKeyAndType.key;

  const convertedInputNode = convertInputNode(input);
  const filteredNode = opFilter({
    arr: convertedInputNode,
    filterFn: constFunction({row: convertedInputNode.type}, ({row}) =>
      opNot({
        bool: opIsNone({
          val: opPick({obj: row, key: constString(workingKey)}),
        }),
      })
    ),
  });

  const stepsNode = opPick({
    obj: filteredNode,
    key: constString(config?.workingSliderKey ?? '_step'),
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
    arr: filteredNode,
    index: constNumber(0),
  });
  const exampleRowRefined = useNodeWithServerType(exampleRow);
  let defaultNode: NodeOrVoidNode = voidNode();
  const currentStep = config?.currentStep ?? -1;
  if (currentStep != null && currentStep >= 0 && workingKey) {
    defaultNode = opPick({
      obj: opFilter({
        arr: filteredNode,
        filterFn: constFunction({row: exampleRowRefined.result.type}, ({row}) =>
          opNumberEqual({
            lhs: opPick({
              obj: row,
              key: constString(config?.workingSliderKey ?? '_step'),
            }),
            rhs: constNumber(currentStep),
          })
        ),
      }),
      key: constString(workingKey),
    });
  }

  const defaultNodeRefined = useNodeWithServerType(defaultNode);

  const {handler} = usePanelStacksForType(
    defaultNodeRefined.result.type,
    config?.workingPanelId
  );

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
            panelSpec={handler as PanelStack}
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

export const Spec: Panel2.PanelSpec<PanelStepperConfigType> = {
  id: 'panel-stepper',
  displayName: 'Stepper',
  Component: PanelStepper,
  ConfigComponent: PanelStepperConfig,
  inputType: LIST_ANY_TYPE,
};

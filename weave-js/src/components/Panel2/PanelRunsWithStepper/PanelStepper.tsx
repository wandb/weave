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
import * as ConfigPanel from '../ConfigPanel';
import * as Panel2 from '../panel';
import {PanelComp2} from '../PanelComp';
import * as PanelLib from '../panellib/libpanel';
import {StackInfo} from '../panellib/stackinfo';

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

const NONE_KEY_AND_TYPE: {[key: string]: Type} = {'<none>': 'any' as Type};

export type PanelStepperProps = Panel2.PanelProps<
  typeof LIST_ANY_TYPE,
  PanelStepperConfigType
>;

const getDefaultWorkingKeyAndType = (
  config: PanelStepperConfigType | undefined,
  propertyKeysAndTypes: {[key: string]: Type}
) => {
  const defaultKey =
    config?.workingKeyAndType?.key &&
    config.workingKeyAndType.key in propertyKeysAndTypes
      ? config.workingKeyAndType.key
      : Object.keys(propertyKeysAndTypes)[0] ?? NONE_KEY_AND_TYPE.key;
  return {
    key: defaultKey,
    type: propertyKeysAndTypes[defaultKey],
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

type additionalProps = {
  safeUpdateConfig: (updates: Partial<PanelStepperConfigType>) => void;
  convertedInputNode: Node;
  filteredNode: Node;
  outputNode: NodeOrVoidNode;
  propertyKeysAndTypes: {[key: string]: Type};
  childPanelStackIds: StackInfo[];
  childPanelHandler: PanelStack | undefined;
};

type PanelStepperEntryProps = PanelStepperProps & {
  isConfigMode: boolean;
};

const PanelStepperEntryComponent: React.FC<PanelStepperEntryProps> = props => {
  const {input, updateConfig, config, isConfigMode} = props;

  const safeUpdateConfig = React.useCallback(
    (updates: Partial<PanelStepperConfigType>) => {
      const needsUpdate = Object.entries(updates).some(
        ([key, value]) => (config as any)?.[key] !== value
      );

      if (needsUpdate) {
        updateConfig(updates);
      }
    },
    [config, updateConfig]
  );

  const convertedInputNode = convertInputNode(input);
  const convertedInputNodeRefined = useNodeWithServerType(convertedInputNode);

  const propertyKeysAndTypes = useMemo(
    () => ({
      ...NONE_KEY_AND_TYPE,
      ...getKeysAndTypesFromPropertyType(convertedInputNodeRefined.result.type),
    }),
    [convertedInputNodeRefined.result.type]
  );

  const workingKeyAndType = getDefaultWorkingKeyAndType(
    config,
    propertyKeysAndTypes
  );

  if (config?.workingKeyAndType == null) {
    safeUpdateConfig({
      workingKeyAndType,
    });
  }

  const filteredNode =
    workingKeyAndType.key === '<none>'
      ? convertedInputNode
      : opFilter({
          arr: convertedInputNode,
          filterFn: constFunction(
            {row: convertedInputNodeRefined.result.type},
            ({row}) =>
              opNot({
                bool: opIsNone({
                  val: opPick({
                    obj: row,
                    key: constString(workingKeyAndType.key),
                  }),
                }),
              })
          ),
        });

  const exampleRow = opIndex({
    arr: filteredNode,
    index: constNumber(0),
  });
  const exampleRowRefined = useNodeWithServerType(exampleRow);
  let outputNode: NodeOrVoidNode = voidNode();
  const currentStep = config?.currentStep ?? -1;
  if (currentStep != null && currentStep >= 0) {
    if (workingKeyAndType.key !== '<none>') {
      outputNode = opPick({
        obj: opFilter({
          arr: filteredNode,
          filterFn: constFunction(
            {row: exampleRowRefined.result.type},
            ({row}) =>
              opNumberEqual({
                lhs: opPick({
                  obj: row,
                  key: constString(config?.workingSliderKey ?? '_step'),
                }),
                rhs: constNumber(currentStep),
              })
          ),
        }),
        key: constString(workingKeyAndType.key),
      });
    } else {
      outputNode = opFilter({
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
      });
    }
  }

  const outputNodeRefined = useNodeWithServerType(outputNode);

  const {stackIds, handler} = usePanelStacksForType(
    outputNodeRefined.result.type,
    config?.workingPanelId ?? undefined,
    {
      disallowedPanels: ['panel-stepper'],
    }
  );

  if (config?.workingPanelId == null) {
    safeUpdateConfig({
      workingPanelId: stackIds[0].id,
    });
  }

  const additionalProps = {
    safeUpdateConfig,
    convertedInputNode,
    filteredNode,
    outputNode: outputNodeRefined.result,
    propertyKeysAndTypes,
    childPanelStackIds: stackIds,
    childPanelHandler: handler,
  };

  return isConfigMode ? (
    <PanelStepperConfig {...props} {...additionalProps} />
  ) : (
    <PanelStepper {...props} {...additionalProps} />
  );
};

const PanelStepperConfigComponent: React.FC<PanelStepperProps> = props => {
  return <PanelStepperEntryComponent {...props} isConfigMode={true} />;
};

const PanelStepperComponent: React.FC<PanelStepperProps> = props => {
  return <PanelStepperEntryComponent {...props} isConfigMode={false} />;
};

export const PanelStepperConfig: React.FC<
  PanelStepperProps & additionalProps
> = props => {
  const {
    safeUpdateConfig,
    config,
    propertyKeysAndTypes,
    outputNode,
    childPanelStackIds,
    childPanelHandler,
  } = props;

  // TODO (nicholaspun-wandb): Used for the "Slider Key" config option below
  // const sliderKeys = useMemo(
  //   () =>
  //     Object.keys(keysAndTypes).filter(key =>
  //       isAssignableTo(keysAndTypes[key], 'number')
  //     ),
  //   [keysAndTypes]
  // );

  const handlerHasConfigComponent =
    childPanelHandler != null &&
    (childPanelHandler.ConfigComponent != null ||
      (PanelLib.isWithChild(childPanelHandler) &&
        childPanelHandler.child.ConfigComponent != null));

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
      <ConfigPanel.ConfigOption label="Property Key">
        <ModifiedDropdownConfigField
          selection
          search
          disabled={props.loading}
          scrolling
          item
          direction="left"
          options={Object.keys(propertyKeysAndTypes).map(key => ({
            key,
            value: key,
            text: key,
          }))}
          value={config?.workingKeyAndType?.key}
          onChange={(e, {value}) => {
            safeUpdateConfig({
              workingKeyAndType: {
                key: value as string,
                type: propertyKeysAndTypes[value as string],
              },
              workingPanelId: undefined,
            });
          }}
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption label="Panel Type">
        <ModifiedDropdownConfigField
          selection
          search
          disabled={props.loading}
          scrolling
          item
          direction="left"
          options={childPanelStackIds.map(si => ({
            text: si.displayName,
            value: si.id,
          }))}
          value={config?.workingPanelId}
          onChange={(e, {value}) =>
            safeUpdateConfig({workingPanelId: value as string})
          }
        />
      </ConfigPanel.ConfigOption>
      {handlerHasConfigComponent && (
        <ConfigPanel.ConfigSection label="Panel Properties">
          <PanelComp2
            input={outputNode}
            inputType={outputNode.type}
            loading={props.loading}
            panelSpec={childPanelHandler as PanelStack}
            configMode={true}
            config={config}
            context={props.context}
            updateConfig={props.updateConfig}
            updateContext={props.updateContext}
            updateInput={props.updateInput}
          />
        </ConfigPanel.ConfigSection>
      )}
    </>
  );
};

export const PanelStepper: React.FC<
  PanelStepperProps & additionalProps
> = props => {
  const {
    safeUpdateConfig,
    config,
    filteredNode,
    outputNode,
    childPanelHandler,
  } = props;

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

  return (
    <>
      {outputNode != null && !isVoidNode(outputNode) && (
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
            input={outputNode}
            inputType={outputNode.type}
            loading={props.loading}
            panelSpec={childPanelHandler as PanelStack}
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
  Component: PanelStepperComponent,
  ConfigComponent: PanelStepperConfigComponent,
  inputType: LIST_ANY_TYPE,
};

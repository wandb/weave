import {useWeaveContext} from '@wandb/weave/context';
import {
  constBoolean,
  constFunction,
  constNumber,
  constString,
  isAssignableTo,
  Node,
  NodeOrVoidNode,
  opBooleanAll,
  opFilter,
  opIndex,
  opIsNone,
  opMap,
  opNot,
  opNumberEqual,
  opNumberIsInteger,
  opOr,
  opPick,
  union,
  voidNode,
} from '@wandb/weave/core';
import React, {useEffect, useMemo, useState} from 'react';

import {useNodeValueExecutor, useNodeWithServerType} from '../../../react';
import {usePanelStacksForType} from '../availablePanels';
import * as Panel2 from '../panel';
import {PanelStepper} from './component';
import {PanelStepperConfig} from './configComponent';
import {
  LIST_ANY_TYPE,
  PanelStepperConfigType,
  PanelStepperEntryProps,
  PanelStepperProps,
} from './types';
import {
  convertInputNode,
  getDefaultWorkingKeyAndType,
  getKeysAndTypesFromPropertyType,
  NONE_KEY_AND_TYPE,
} from './util';

const useIntegralChecks = (
  propertyKeys: string[],
  inputNode: Node
): {[key: string]: boolean} => {
  const [results, setResults] = useState<{[key: string]: boolean}>({});
  const executor = useNodeValueExecutor();
  const inputNodeRefined = useNodeWithServerType(inputNode);

  const hasRunRef = React.useRef(false);
  useEffect(() => {
    if (hasRunRef.current || propertyKeys.length === 0) {
      return;
    }

    const checkKeys = async () => {
      const newResults: {[key: string]: boolean} = {};

      const promises = propertyKeys.map(async (key: string) => {
        const node = opBooleanAll({
          values: opMap({
            arr: inputNode,
            mapFn: constFunction({row: inputNodeRefined.result.type}, ({row}) =>
              opOr({
                lhs: opNumberIsInteger({
                  number: opPick({
                    obj: row,
                    key: constString(key),
                  }),
                }),
                rhs: opIsNone({
                  val: opPick({
                    obj: row,
                    key: constString(key),
                  }),
                }),
              })
            ),
          }),
        });

        try {
          const result = await executor(node);
          return {key, result};
        } catch (e) {
          console.error(e);
          return {key, result: false};
        }
      });

      const checkResults = await Promise.all(promises);

      checkResults.forEach(({key, result}) => {
        newResults[key] = result;
      });

      hasRunRef.current = true;
      setResults(newResults);
    };

    checkKeys();
  }, [propertyKeys, executor, inputNode, inputNodeRefined]);

  return results;
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

  const convertedInputNode = convertInputNode(input as Node);
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

  const workingInputNode =
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
    arr: workingInputNode,
    index: constNumber(0),
  });
  const exampleRowRefined = useNodeWithServerType(exampleRow);
  let outputNode: NodeOrVoidNode = voidNode();
  if (config?.currentStep != null && config?.workingSliderKey != null) {
    const resultsAtStepNode = opFilter({
      arr: workingInputNode,
      filterFn: constFunction({row: exampleRowRefined.result.type}, ({row}) =>
        opNumberEqual({
          lhs: opPick({
            obj: row,
            key: constString(config?.workingSliderKey!),
          }),
          rhs: constNumber(config?.currentStep!),
        })
      ),
    });

    outputNode =
      workingKeyAndType.key === '<none>'
        ? resultsAtStepNode
        : opPick({
            obj: resultsAtStepNode,
            key: constString(workingKeyAndType.key),
          });
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

  const numericalKeys = Object.keys(propertyKeysAndTypes).filter(
    key =>
      isAssignableTo(propertyKeysAndTypes[key], union(['none', 'number'])) &&
      !['loss', 'accuracy', 'precision', 'recall'].some(metric =>
        key.includes(metric)
      )
  );

  const isIntegerResults = useIntegralChecks(numericalKeys, workingInputNode);

  useEffect(() => {
    if (Object.keys(isIntegerResults).length === 0) {
      return;
    }

    const validSliderKeys = numericalKeys.filter(
      key => isIntegerResults[key] === true
    );

    const currentValidKeys = config?.validSliderKeys || [];
    const currentWorkingKey = config?.workingSliderKey;

    const keysChanged =
      validSliderKeys.length !== currentValidKeys.length ||
      validSliderKeys.some(key => !currentValidKeys.includes(key));

    const needsNewWorkingKey =
      (validSliderKeys.length > 0 && !currentWorkingKey) ||
      (currentWorkingKey && !validSliderKeys.includes(currentWorkingKey));

    if (keysChanged || needsNewWorkingKey) {
      const update: Partial<PanelStepperConfigType> = {
        validSliderKeys,
      };

      if (needsNewWorkingKey) {
        update.workingSliderKey =
          validSliderKeys.length > 0 ? validSliderKeys[0] : null;
      }

      safeUpdateConfig(update);
    }
  }, [
    numericalKeys,
    isIntegerResults,
    config?.validSliderKeys,
    config?.workingSliderKey,
    safeUpdateConfig,
  ]);

  const additionalProps = {
    safeUpdateConfig,
    convertedInputNode,
    filteredNode: workingInputNode,
    outputNode: outputNodeRefined.result,
    propertyKeysAndTypes,
    childPanelStackIds: stackIds,
    childPanelHandler: handler,
  };

  const noValidSliderKeysEmptyState = () => (
    <div
      style={{
        height: '100%',
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#666',
        fontSize: '14px',
      }}>
      Panel currently unsupported for custom step metrics. Please use an
      expression that returns the pre-defined step metric (_step) for now
    </div>
  );

  const renderConfigComponent = () =>
    config?.validSliderKeys != null ? (
      <PanelStepperConfig {...props} {...additionalProps} />
    ) : (
      noValidSliderKeysEmptyState()
    );

  const renderPanelComponent = () =>
    config?.validSliderKeys != null ? (
      <PanelStepper {...props} {...additionalProps} />
    ) : (
      noValidSliderKeysEmptyState()
    );

  return isConfigMode ? renderConfigComponent() : renderPanelComponent();
};

const PanelStepperConfigComponent: React.FC<PanelStepperProps> = props => {
  return <PanelStepperEntryComponent {...props} isConfigMode={true} />;
};

const PanelStepperComponent: React.FC<PanelStepperProps> = props => {
  return <PanelStepperEntryComponent {...props} isConfigMode={false} />;
};

export const Spec: Panel2.PanelSpec<PanelStepperConfigType> = {
  id: 'panel-stepper',
  displayName: 'Stepper',
  Component: PanelStepperComponent,
  ConfigComponent: PanelStepperConfigComponent,
  inputType: LIST_ANY_TYPE,
};

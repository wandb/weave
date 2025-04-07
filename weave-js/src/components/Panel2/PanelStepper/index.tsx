import {LIST_ANY_TYPE} from '@wandb/weave/common/types/list';
import {
  constFunction,
  constNumber,
  constString,
  Node,
  NodeOrVoidNode,
  opFilter,
  opIndex,
  opIsNone,
  opNot,
  opNumberEqual,
  opPick,
  voidNode,
} from '@wandb/weave/core';
import React, {useMemo} from 'react';

import {useNodeWithServerType} from '../../../react';
import {usePanelStacksForType} from '../availablePanels';
import * as Panel2 from '../panel';
import {PanelStepper} from './component';
import {PanelStepperConfig} from './configComponent';
import {
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
  const currentStep = config?.currentStep ?? -1;
  const resultsAtStepNode = opFilter({
    arr: workingInputNode,
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
  let outputNode: NodeOrVoidNode = voidNode();
  if (currentStep != null && currentStep >= 0) {
    if (workingKeyAndType.key !== '<none>') {
      outputNode = opPick({
        obj: resultsAtStepNode,
        key: constString(workingKeyAndType.key),
      });
    } else {
      outputNode = resultsAtStepNode;
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
    filteredNode: workingInputNode,
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

export const Spec: Panel2.PanelSpec<PanelStepperConfigType> = {
  id: 'panel-stepper',
  displayName: 'Stepper',
  Component: PanelStepperComponent,
  ConfigComponent: PanelStepperConfigComponent,
  inputType: LIST_ANY_TYPE,
};

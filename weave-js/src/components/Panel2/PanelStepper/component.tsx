import SliderInput from '@wandb/weave/common/components/elements/SliderInput';
import {constString, isVoidNode, opPick} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import React, {useEffect} from 'react';

import {PanelStack} from '../availablePanels';
import {PanelComp2} from '../PanelComp';
import {additionalProps, PanelStepperProps} from './types';

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

import React from 'react';

import {PanelStack} from '../availablePanels';
import * as ConfigPanel from '../ConfigPanel';
import {ModifiedDropdownConfigField} from '../ConfigPanel';
import {PanelComp2} from '../PanelComp';
import * as PanelLib from '../panellib/libpanel';
import {additionalProps, PanelStepperProps} from './types';

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

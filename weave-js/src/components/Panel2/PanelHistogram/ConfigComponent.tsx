import React from 'react';

import {
  ConfigOption,
  ConfigSection,
  ModifiedDropdownConfigField,
} from '../ConfigPanel';
import {usePanelContext} from '../PanelContext';
import {defaultConfig, PanelHistogramProps} from './common';

/* eslint-disable no-template-curly-in-string */

const PanelHistogramConfig: React.FC<PanelHistogramProps> = props => {
  const {updateConfig} = props;
  const {dashboardConfigOptions} = usePanelContext();
  const config = props.config ?? defaultConfig();
  // TODO(np): Need to fix upstream bug where we are getting var node n
  // here
  // const dataExtent = useExtentFromData(props.input);
  const dataExtent = [0, 1];

  const innerConfig =
    config.mode === 'auto' ? (
      <></>
    ) : config.mode === 'bin-size' ? (
      <>
        <ConfigOption label={'Bin size'}>
          <ModifiedDropdownConfigField
            selection
            allowAdditions
            value={config.binSize ?? 'Auto'}
            options={['Auto'].map(o => ({
              key: o,
              value: o,
              text: o,
            }))}
            onChange={(e, {value}) => {
              let newValue =
                value === 'Auto' ? undefined : Math.max(0, Number(value));
              if (isNaN(newValue ?? NaN)) {
                newValue = undefined;
              }
              updateConfig({binSize: newValue});
            }}
          />
        </ConfigOption>
      </>
    ) : config.mode === 'num-bins' ? (
      <>
        <ConfigOption label={'Number of bins'}>
          <ModifiedDropdownConfigField
            selection
            allowAdditions
            value={config.nBins ?? 'Default'}
            options={['Default', 10, 25, 50, 100, 250, 500].map(o => ({
              key: o,
              value: o,
              text: o,
            }))}
            onChange={(e, {value}) => {
              let newValue =
                value === 'Default'
                  ? undefined
                  : Math.round(Math.max(1, Math.min(1000, Number(value))));
              if (isNaN(newValue ?? NaN)) {
                newValue = undefined;
              }
              updateConfig({nBins: newValue});
            }}
          />
        </ConfigOption>
      </>
    ) : (
      <></>
    );

  return (
    <ConfigSection label={`Properties`}>
      {dashboardConfigOptions}
      <ConfigOption label={'Bin mode'}>
        <ModifiedDropdownConfigField
          selection
          value={config.mode ?? 'auto'}
          options={[
            ['auto', 'Auto'],
            ['bin-size', 'Bin size'],
            ['num-bins', 'Number of bins'],
          ].map(o => ({
            key: o[0],
            value: o[0],
            text: o[1],
          }))}
          onChange={(e, {value}) => {
            updateConfig({mode: value as any});
          }}
        />
      </ConfigOption>
      {innerConfig}
      <ConfigOption label={'Min extent'}>
        <ModifiedDropdownConfigField
          selection
          allowAdditions
          value={config.extent?.[0] ?? 'Auto'}
          options={['Auto', 0].map(o => ({
            key: o,
            value: o,
            text: o,
          }))}
          onChange={(e, {value}) => {
            let newValue =
              value === 'Auto'
                ? undefined
                : Math.min(config.extent?.[1] ?? Infinity, Number(value));
            if (isNaN(newValue ?? NaN)) {
              newValue = undefined;
            }
            updateConfig({extent: [newValue, config.extent?.[0]]});
          }}
        />
      </ConfigOption>
      <ConfigOption label={'Max extent'}>
        <ModifiedDropdownConfigField
          selection
          allowAdditions
          value={config.extent?.[1] ?? 'Auto'}
          options={[
            'Auto',
            Math.pow(10, Math.ceil(Math.log10(dataExtent?.[1] ?? 1))),
          ].map(o => ({
            key: o,
            value: o,
            text: o,
          }))}
          onChange={(e, {value}) => {
            let newValue =
              value === 'Auto'
                ? undefined
                : Math.max(config.extent?.[0] ?? -Infinity, Number(value));
            if (isNaN(newValue ?? NaN)) {
              newValue = undefined;
            }
            updateConfig({extent: [config.extent?.[0], newValue]});
          }}
        />
      </ConfigOption>
    </ConfigSection>
  );
};

export default PanelHistogramConfig;

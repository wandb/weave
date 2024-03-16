import {MOON_500} from '@wandb/weave/common/css/color.styles';
import React, {useCallback, useContext} from 'react';

import {formatNumber} from '../../core/util/number';
import * as CGReact from '../../react';
import {IconHelpAlt} from '../Icon';
import {Tooltip} from '../Tooltip';
import * as ConfigPanel from './ConfigPanel';
import * as Panel2 from './panel';
import {Panel2Loader} from './PanelComp';
import {WeaveFormatContext} from './WeaveFormatContext';

const CustomFormatHelp = () => {
  return (
    <Tooltip
      trigger={
        <IconHelpAlt
          color={MOON_500}
          width={16}
          height={16}
          style={{margin: 4}}
        />
      }
      content="Syntax is inspired by Python's Format Specification Mini-Language. Supports precision, width with leading zeros, and commas for grouping. e.g. Value 1234 with format '+010,.1f' -> '+001,234.0'"
    />
  );
};

const PanelNumberConfig: React.FC<PanelNumberProps> = props => {
  const {config, updateConfig} = props;
  const updateFormat = useCallback(
    (propFormat: string) => {
      updateConfig({
        ...config,
        propFormat,
      });
    },
    [updateConfig, config]
  );

  const format = config?.propFormat ?? 'Automatic';
  const formatDropdownValue = format.startsWith('*')
    ? 'Custom'
    : format.startsWith('$')
    ? 'Currency'
    : format;
  const customFormatValue = format.startsWith('*') ? format.slice(1) : format;
  return (
    <div>
      <ConfigPanel.ConfigOption label="Format">
        <ConfigPanel.ModifiedDropdownConfigField
          selection
          options={[
            {
              text: 'Automatic',
              value: 'Automatic',
            },
            {
              text: 'Number',
              value: 'Number',
              description: '1,000.12',
            },
            {
              text: 'Percent',
              value: 'Percent',
              description: '10.12%',
            },
            {
              text: 'Scientific',
              value: 'Scientific',
              description: '1.000120e+03',
            },
            {
              text: 'Compact',
              value: 'Compact',
              description: '1K',
            },
            {
              text: 'Currency', // TODO: Handle currencies other than USD
              value: 'Currency',
              description: '$1,000.12',
            },
            {
              text: 'Custom',
              value: 'Custom',
            },
          ]}
          value={formatDropdownValue}
          onChange={(e, {value}) => {
            const newValue = typeof value === 'string' ? value : 'Automatic';
            if (newValue === 'Custom') {
              updateFormat('*');
            } else if (newValue === 'Currency') {
              updateFormat('$USD');
            } else {
              updateFormat(newValue);
            }
          }}
        />
      </ConfigPanel.ConfigOption>
      {formatDropdownValue === 'Custom' && (
        <ConfigPanel.ConfigOption
          label="Format expr"
          postfixComponent={<CustomFormatHelp />}>
          <ConfigPanel.TextInputConfigField
            dataTest="label"
            value={customFormatValue}
            label=""
            onChange={(event, {value}) => {
              // TODO: Validate format and show indication if invalid
              updateFormat('*' + value.trim());
            }}
          />
        </ConfigPanel.ConfigOption>
      )}
    </div>
  );
};

const inputType = {
  type: 'union' as const,
  members: ['none' as const, 'number' as const],
};
type PanelNumberProps = Panel2.PanelProps<
  typeof inputType,
  {propFormat: string}
>;
type PanelNumberExtraProps = {
  textAlign?: 'left' | 'right' | 'center' | 'justify' | 'initial' | 'inherit';
};

export const PanelNumber: React.FC<
  PanelNumberProps & PanelNumberExtraProps
> = props => {
  const {numberFormat} = useContext(WeaveFormatContext);
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  if (nodeValueQuery.loading) {
    return <Panel2Loader />;
  }
  const textAlign = numberFormat.textAlign ?? props.textAlign ?? 'center';
  const justifyContent = numberFormat.justifyContent ?? 'space-around';
  const alignContent = numberFormat.alignContent ?? 'space-around';
  const padding = numberFormat.padding ?? '0';

  return (
    <div
      data-test-weave-id="number"
      style={{
        textAlign,
        alignContent,
        justifyContent,
        padding,
        width: '100%',
        height: '100%',
        overflowX: 'hidden',
        overflowY: 'auto',
        margin: 'auto',
        wordBreak: 'normal',
        display: 'flex',
        flexDirection: 'column',
        alignItems: textAlign === 'center' ? 'center' : 'normal',
      }}>
      {nodeValueQuery.result == null
        ? '-'
        : formatNumber(
            nodeValueQuery.result,
            props.config?.propFormat ?? 'Automatic'
          )}
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'number',
  icon: 'number',
  category: 'Primitive',
  Component: PanelNumber,
  ConfigComponent: PanelNumberConfig,
  inputType,
};

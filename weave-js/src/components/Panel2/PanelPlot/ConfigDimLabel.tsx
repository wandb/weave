import * as globals from '@wandb/weave/common/css/globals.styles';
import React from 'react';

import * as ConfigPanel from '../ConfigPanel';
import {DASHBOARD_DIM_NAME_MAP} from './plotState';
import {DIM_NAME_MAP, DimComponentInputType} from './types';

export const ConfigDimLabel: React.FC<
  Omit<DimComponentInputType, 'extraOptions'> & {
    postfixComponent?: React.ReactElement;
    multiline?: boolean;
    redesignedPlotConfigEnabled?: boolean;
  }
> = props => {
  const dimName = props.dimension.name;
  const seriesIndexStr =
    props.isShared || props.config.series.length === 1
      ? ''
      : ` ${props.config.series.indexOf(props.dimension.series) + 1}`;
  const label = props.redesignedPlotConfigEnabled
    ? DASHBOARD_DIM_NAME_MAP[dimName]
    : DIM_NAME_MAP[dimName] + seriesIndexStr;

  return (
    <div
      style={{
        paddingLeft: 10 * props.indentation,
        borderLeft:
          props.indentation > 0 && props.redesignedPlotConfigEnabled
            ? `2px solid ${globals.MOON_200}`
            : 'none',
      }}>
      <ConfigPanel.ConfigOption
        label={label}
        data-test={`${props.dimension.name}-dim-config`}
        postfixComponent={props.postfixComponent}
        multiline={props.multiline}>
        {props.children}
      </ConfigPanel.ConfigOption>
    </div>
  );
};

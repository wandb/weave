import React from 'react';

import * as Colors from '../../../../common/css/color.styles';
import {Icon, IconNames} from '../../../Icon';
import {Tooltip} from '../../../Tooltip';

type CellValueBooleanProps = {
  value: boolean;
};

export const CellValueBoolean = ({value}: CellValueBooleanProps) => {
  const label = value ? 'True' : 'False';
  return (
    <div
      style={{
        height: '100%',
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
      <Tooltip trigger={<BooleanIcon value={value} />} content={label} />
    </div>
  );
};

export const BooleanIcon = ({value}: {value: boolean}) => {
  const color = value ? Colors.GREEN_600 : Colors.RED_600;
  const icon = value ? IconNames.Checkmark : IconNames.Close;
  return <Icon color={color} name={icon} />;
};

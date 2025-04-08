import React from 'react';

import * as Colors from '../../../../common/css/color.styles';
import {Icon} from '../../../Icon';
import {Tooltip} from '../../../Tooltip';

type CellValueBooleanProps = {
  value: boolean;
};

export const CellValueBoolean = ({value}: CellValueBooleanProps) => {
  const color = value ? Colors.GREEN_600 : Colors.RED_600;
  const label = value ? 'True' : 'False';
  const icon = value ? 'checkmark' : 'close';
  return (
    <div
      style={{
        height: '100%',
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
      <Tooltip trigger={<Icon color={color} name={icon} />} content={label} />
    </div>
  );
};

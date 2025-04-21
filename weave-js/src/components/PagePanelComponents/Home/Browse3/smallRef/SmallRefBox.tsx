import {Box} from '@mui/material';
import React, {FC} from 'react';

import {hexToRGB, MOON_300} from '../../../../../common/css/globals.styles';
import {Icon, IconName} from '../../../../Icon';

export const SmallRefBox: FC<{
  iconName: IconName;
  text: string;
  iconOnly?: boolean;
  isDeleted?: boolean;
}> = ({iconName, text, iconOnly = false, isDeleted = false}) => (
  <Box display="flex" alignItems="center">
    <Box
      mr="4px"
      bgcolor={hexToRGB(MOON_300, 0.48)}
      sx={{
        height: '22px',
        width: '22px',
        borderRadius: '16px',
        display: 'flex',
        flex: '0 0 22px',
        justifyContent: 'center',
        alignItems: 'center',
      }}>
      <Icon name={iconName} width={14} height={14} />
    </Box>
    {!iconOnly && (
      <Box
        sx={{
          height: '22px',
          flex: 1,
          minWidth: 0,
          overflow: 'hidden',
          whiteSpace: 'nowrap',
          textOverflow: 'ellipsis',
          textDecoration: isDeleted ? 'line-through' : 'none',
        }}>
        {text}
      </Box>
    )}
  </Box>
);

import {Box, Typography} from '@mui/material';
import {TEAL_500} from '@wandb/weave/common/css/color.styles';
import React from 'react';
import {Link} from 'react-router-dom';

import {Icon} from '../../../../Icon';

const VIEW_DATASET_LINK_STYLES = {
  color: TEAL_500,
  textDecoration: 'none',
  fontSize: '16px',
  fontFamily: 'Source Sans Pro',
} as const;

interface DatasetPublishToastProps {
  url: string;
  message: string;
}

export const DatasetPublishToast: React.FC<DatasetPublishToastProps> = ({
  url,
  message,
}) => (
  <Box sx={{display: 'flex', flexDirection: 'column', gap: 1}}>
    <Box sx={{display: 'flex', alignItems: 'center', gap: 1.5}}>
      <Icon name="checkmark-circle" width={24} height={24} color={TEAL_500} />
      <Typography
        sx={{color: 'white', fontSize: '16px', fontFamily: 'Source Sans Pro'}}>
        {message}
      </Typography>
    </Box>
    <Link to={url} style={VIEW_DATASET_LINK_STYLES}>
      View the dataset
    </Link>
  </Box>
);

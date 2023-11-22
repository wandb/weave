import {Typography} from '@mui/material';
import React, {FC} from 'react';
import {useParams} from 'react-router-dom';

import {
  Browse2RootObjectType,
  Browse2RootObjectTypeParams,
} from './Browse2RootObjectType';
import {Paper} from './CommonLib';
import {PageEl} from './CommonLib';
import {PageHeader} from './CommonLib';

export const Browse2ObjectTypePage: FC = props => {
  const params = useParams<Browse2RootObjectTypeParams>();
  return (
    <PageEl>
      <PageHeader objectType="Object Type" objectName={params.rootType} />
      <Paper>
        <Typography variant="h6" gutterBottom>
          {params.rootType + 's'}
        </Typography>
        <Browse2RootObjectType {...params} />
      </Paper>
    </PageEl>
  );
};

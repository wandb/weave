import {Typography} from '@mui/material';
import {useIsAuthenticated} from '@wandb/weave/context/WeaveViewerContext';
import React, {FC, useCallback, useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {URL_BROWSE3} from '../../../../urls';
import * as query from '../query';
import {PageEl, PageHeader, Paper} from './CommonLib';
import {LinkTable} from './LinkTable';

export const Browse2HomePage: FC = props => {
  const isAuthenticated = useIsAuthenticated();
  const userEntities = query.useUserEntities(isAuthenticated);
  const rows = useMemo(
    () =>
      userEntities.result.map((entityName, i) => ({
        id: i,
        name: entityName,
      })),
    [userEntities.result]
  );
  const history = useHistory();
  const handleRowClick = useCallback(
    (row: any) => {
      const entityName = row.name;
      history.push(`/${URL_BROWSE3}/${entityName}`);
    },
    [history]
  );
  return (
    <PageEl>
      <PageHeader objectType="Home" />
      <Paper>
        <Typography variant="h6" gutterBottom>
          Entities
        </Typography>
        <LinkTable rows={rows} handleRowClick={handleRowClick} />
      </Paper>
    </PageEl>
  );
};

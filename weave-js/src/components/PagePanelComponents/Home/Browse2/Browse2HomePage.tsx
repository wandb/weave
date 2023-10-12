import React, {FC, useCallback, useMemo} from 'react';
import {useHistory} from 'react-router-dom';
import {URL_BROWSE2} from '../../../../urls';
import {useIsAuthenticated} from '@wandb/weave/context/WeaveViewerContext';
import * as query from '../query';
import {Typography} from '@mui/material';
import {LinkTable} from './LinkTable';
import {Paper, PageHeader, PageEl} from './CommonLib';

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
      history.push(`/${URL_BROWSE2}/${entityName}`);
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

import {Typography} from '@mui/material';
import React, {FC, useCallback, useMemo} from 'react';
import {useHistory, useParams} from 'react-router-dom';

import {URL_BROWSE3} from '../../../../urls';
import * as query from '../query';
import {PageEl, PageHeader, Paper} from './CommonLib';
import {LinkTable} from './LinkTable';

interface Browse2EntityParams {
  entity: string;
}

export const Browse2EntityPage: FC = props => {
  const params = useParams<Browse2EntityParams>();
  const entityProjects = query.useProjectsForEntity(params.entity);
  const rows = useMemo(
    () =>
      entityProjects.result.map((entityProject, i) => ({
        id: i,
        name: entityProject,
      })),
    [entityProjects.result]
  );
  const history = useHistory();
  const handleRowClick = useCallback(
    (row: any) => {
      const projectName = row.name;
      history.push(`/${URL_BROWSE3}/${params.entity}/${projectName}`);
    },
    [history, params.entity]
  );
  return (
    <PageEl>
      <PageHeader objectType="Entity" objectName={params.entity} />
      <Paper>
        <Typography variant="h6" gutterBottom>
          Projects
        </Typography>
        <LinkTable rows={rows} handleRowClick={handleRowClick} />
      </Paper>
    </PageEl>
  );
};

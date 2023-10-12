import React, {FC, useCallback, useMemo} from 'react';
import {useParams, useHistory} from 'react-router-dom';
import {URL_BROWSE2} from '../../../../urls';
import * as query from '../query';
import {Typography} from '@mui/material';
import {LinkTable} from './LinkTable';
import {Paper, PageHeader, PageEl} from './CommonLib';

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
      history.push(`/${URL_BROWSE2}/${params.entity}/${projectName}`);
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

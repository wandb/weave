import {Box, Grid, Typography} from '@mui/material';
import {useWeaveContext} from '@wandb/weave/context';
import {constString, opGet} from '@wandb/weave/core';
import React, {FC, useCallback, useMemo} from 'react';
import {useHistory, useParams} from 'react-router-dom';

import * as query from '../query';
import {Browse2RootObjectType} from './Browse2RootObjectType';
import {Link, makeObjRefUri, Paper} from './CommonLib';
import {PageEl} from './CommonLib';
import {PageHeader} from './CommonLib';
import {LinkTable} from './LinkTable';

const Browse2Boards: FC<{entity: string; project: string}> = ({
  entity,
  project,
}) => {
  const weave = useWeaveContext();
  const objectsInfo = query.useProjectObjectsOfType(entity, project, 'Panel');
  const rows = useMemo(
    () =>
      (objectsInfo.result ?? []).map((row, i) => ({
        id: i,
        _name: row.name,
        name: row.name + ' ⮕',
      })),
    [objectsInfo.result]
  );
  const history = useHistory();
  const handleRowClick = useCallback(
    (row: any) => {
      const boardNode = opGet({
        uri: constString(
          makeObjRefUri({
            entity,
            project,
            objName: row._name,
            objVersion: 'latest',
          })
        ),
      });
      return history.push(
        `/?exp=${encodeURIComponent(weave.expToString(boardNode))}`
      );
    },
    [entity, project, history, weave]
  );
  return (
    <>
      <LinkTable rows={rows} handleRowClick={handleRowClick} />
    </>
  );
};

interface Browse2ProjectParams {
  entity: string;
  project: string;
}

export const Browse2ProjectPage: FC = props => {
  const params = useParams<Browse2ProjectParams>();
  const rootTypeCounts = query.useProjectAssetCountGeneral(
    params.entity,
    params.project
  );
  const rows = useMemo(
    () =>
      (rootTypeCounts.result ?? [])
        .filter(
          typeInfo =>
            typeInfo.name !== 'stream_table' &&
            typeInfo.name !== 'Panel' &&
            typeInfo.name !== 'OpDef' &&
            typeInfo.name !== 'wandb-history'
        )
        .map((row, i) => ({
          id: i,

          // TODO: Major hack to rename list to Table
          name: row.name === 'list' ? 'Table' : row.name,
          'object count': row['object count'],
        })),
    [rootTypeCounts.result]
  );
  const history = useHistory();
  const handleRowClick = useCallback(
    (row: any) => {
      history.push(`/${params.entity}/${params.project}/${row.name}`);
    },
    [history, params.entity, params.project]
  );
  return (
    <PageEl>
      <PageHeader objectType="Project" objectName={params.project} />
      <Grid container spacing={3}>
        <Grid item xs={12} sm={6}>
          <Box mb={4}>
            <Paper>
              <Typography variant="h6" gutterBottom>
                Object Types
              </Typography>
              <LinkTable rows={rows} handleRowClick={handleRowClick} />
            </Paper>
          </Box>
          <Paper>
            <Typography variant="h6" gutterBottom>
              Boards
            </Typography>
            <Browse2Boards entity={params.entity} project={params.project} />
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6}>
          <Paper>
            <Typography
              variant="h6"
              gutterBottom
              display="flex"
              justifyContent="space-between">
              Functions
              <Typography variant="h6" component="span">
                <Link to={`/${params.entity}/${params.project}/trace`}>
                  [See all runs]
                </Link>
              </Typography>
            </Typography>
            <Browse2RootObjectType
              entity={params.entity}
              project={params.project}
              rootType="OpDef"
            />
          </Paper>
        </Grid>
      </Grid>
      <div style={{marginBottom: 12}}></div>
      <div style={{marginBottom: 12}}></div>
    </PageEl>
  );
};

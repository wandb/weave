import {Typography} from '@mui/material';
import {formatRelativeTime} from '@wandb/weave/util';
import React, {FC, useCallback, useMemo} from 'react';
import {useHistory, useParams} from 'react-router-dom';

import * as query from '../query';
import {Paper} from './CommonLib';
import {PageEl} from './CommonLib';
import {PageHeader} from './CommonLib';
import {LinkTable} from './LinkTable';

interface Browse2RootObjectParams {
  entity: string;
  project: string;
  rootType: string;
  objName: string;
  objVersion: string;
}
export const Browse2ObjectPage: FC = props => {
  const params = useParams<Browse2RootObjectParams>();
  // const aliases = query.useObjectAliases(
  //   params.entity,
  //   params.project,
  //   params.objName
  // );
  const versionNames = query.useObjectVersions(
    params.entity,
    params.project,
    params.objName
  );

  const rows = useMemo(
    () =>
      (versionNames.result ?? []).map((row, i) => ({
        id: i,
        ...row,
      })),
    [versionNames.result]
  );

  const history = useHistory();
  const handleRowClick = useCallback(
    (row: any) => {
      history.push(
        `/${params.entity}/${params.project}/${params.rootType}/${params.objName}/${row.digest}`
      );
    },
    [history, params.entity, params.objName, params.project, params.rootType]
  );
  return (
    <PageEl>
      <PageHeader objectType={params.rootType} objectName={params.objName} />
      {/* <div>
              Aliases
              {aliases.result.map(alias => (
                <div key={alias}>
                  <Link
                    to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}/${alias}`}>
                    {alias}
                  </Link>
                </div>
              ))}
            </div> */}
      <div>
        <Paper>
          <Typography variant="h6" gutterBottom>
            Versions
          </Typography>
          <LinkTable
            rows={rows}
            handleRowClick={handleRowClick}
            columns={[
              {
                field: 'digest',
                width: 200,
              },

              {
                field: 'createdAt',
                headerName: 'Created At',
                width: 200,
                valueFormatter: (linkParams: any) =>
                  formatRelativeTime(linkParams?.value),
              },
            ]}
          />
        </Paper>
        {/* {versionNames.result.map(version => (
              <div key={version}>
                <Link
                  to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}/${version}`}>
                  {version}
                </Link>
              </div>
            ))} */}
      </div>
    </PageEl>
  );
};

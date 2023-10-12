import React, {FC, useCallback, useMemo} from 'react';
import {useParams, useHistory} from 'react-router-dom';
import {URL_BROWSE2} from '../../../../urls';
import * as query from '../query';
import {Paper} from './CommonLib';
import {Typography} from '@mui/material';
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
        name: row,
      })),
    [versionNames.result]
  );
  const history = useHistory();
  const handleRowClick = useCallback(
    (row: any) => {
      history.push(
        `/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}/${row.name}`
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
          <LinkTable rows={rows} handleRowClick={handleRowClick} />
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

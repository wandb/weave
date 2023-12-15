import React, {FC, useCallback, useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import * as query from '../query';
import {LinkTable} from './LinkTable';

export interface Browse2RootObjectTypeParams {
  entity: string;
  project: string;
  rootType: string;
}

export const Browse2RootObjectType: FC<Browse2RootObjectTypeParams> = ({
  entity,
  project,
  rootType,
}) => {
  const objectsInfo = query.useProjectObjectsOfType(entity, project, rootType);
  const rows = useMemo(
    () =>
      (objectsInfo.result ?? []).map((row, i) => ({
        id: i,
        ...row,
      })),
    [objectsInfo.result]
  );
  const history = useHistory();
  const handleRowClick = useCallback(
    (row: any) => {
      history.push(`/${entity}/${project}/${rootType}/${row.name}`);
    },
    [history, entity, project, rootType]
  );
  return (
    <>
      <LinkTable rows={rows} handleRowClick={handleRowClick} />
    </>
  );
};

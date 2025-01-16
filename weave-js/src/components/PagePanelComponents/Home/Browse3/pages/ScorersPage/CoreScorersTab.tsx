import React from 'react';

import {FilterableObjectVersionsTable} from '../ObjectsPage/ObjectVersionsTable';

export const ProgrammaticScorersTab: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  return (
    <FilterableObjectVersionsTable
      entity={entity}
      project={project}
      objectTitle="Scorer"
      hideCategoryColumn
      initialFilter={{
        baseObjectClass: 'Scorer',
      }}
    />
  );
};

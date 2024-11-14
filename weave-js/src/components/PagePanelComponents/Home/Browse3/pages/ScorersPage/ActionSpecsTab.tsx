import React from 'react';

import {FilterableObjectVersionsTable} from '../ObjectVersionsPage';
export const ActionSpecsTab: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  return (
      <FilterableObjectVersionsTable
        entity={entity}
        project={project}
        initialFilter={{
          baseObjectClass: 'ActionSpec',
        }}
      />
  );
};

import React from 'react';

import {EMPTY_PROPS_PROGRAMMATIC_SCORERS} from '../common/EmptyContent';
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
      propsEmpty={EMPTY_PROPS_PROGRAMMATIC_SCORERS}
    />
  );
};

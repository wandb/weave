import React from 'react';

import {FilterableObjectVersionsTable} from '../ObjectVersionsPage';

export const AnnotationsTab: React.FC<{
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
        baseObjectClass: 'AnnotationSpec',
      }}
    />
  );
};

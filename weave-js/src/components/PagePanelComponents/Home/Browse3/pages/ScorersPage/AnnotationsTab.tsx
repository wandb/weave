import React from 'react';

import {EMPTY_PROPS_ANNOTATIONS} from '../common/EmptyContent';
import {FilterableObjectVersionsTable} from '../ObjectsPage/ObjectVersionsTable';

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
      propsEmpty={EMPTY_PROPS_ANNOTATIONS}
    />
  );
};
